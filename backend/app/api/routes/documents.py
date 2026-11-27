import hashlib
import json
import re
import uuid
import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.redis_client import cache_get_json, cache_set_json, cache_delete_pattern
from app.core.observability import add_metric
from app.database.session import get_db
from app.models.conversation import Conversation, Message
from app.models.events import OutboxEvent
from app.models.document import Document, DocumentChunk
from app.models.membership import WorkspaceMembership
from app.models.user import User
from app.schemas.documents import Citation, ChatRequest, ChatResponse, DocumentResponse
from app.services.document_pipeline import (
    chunk_pages, embed_texts, extract_text, generate_answer,
)

router = APIRouter(tags=["Documents and RAG"])
ALLOWED = {"application/pdf": ".pdf", "text/plain": ".txt"}


async def require_workspace(workspace_id: uuid.UUID, user: User, db: AsyncSession):
    membership = await db.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user.id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="Workspace membership required")
    return membership


def _stored_path(workspace_id: uuid.UUID, storage_key: str) -> Path:
    # storage_key is generated server-side and never accepted from a request.
    return Path(settings.STORAGE_ROOT) / str(workspace_id) / storage_key


@router.post("/workspaces/{workspace_id}/documents", response_model=DocumentResponse, status_code=202)
async def upload_document(workspace_id: uuid.UUID, file: UploadFile = File(...),
                          user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    membership = await require_workspace(workspace_id, user, db)
    if membership.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewer role cannot upload documents")

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    suffix = Path(file.filename or "").suffix.lower()
    if content_type not in ALLOWED or suffix != ALLOWED[content_type]:
        raise HTTPException(status_code=415, detail="Only PDF and UTF-8 TXT files are supported.")

    raw = await file.read(settings.MAX_UPLOAD_BYTES + 1)
    if not raw:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(raw) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 20 MB upload limit.")
    if content_type == "application/pdf" and not raw.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="The uploaded file is not a valid PDF.")
    if content_type == "text/plain":
        try:
            raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="TXT files must use UTF-8 encoding.")

    storage_dir = Path(settings.STORAGE_ROOT) / str(workspace_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_key = f"{uuid.uuid4().hex}{ALLOWED[content_type]}"
    path = storage_dir / storage_key
    path.write_bytes(raw)

    doc = Document(
        workspace_id=workspace_id,
        uploaded_by=user.id,
        original_filename=Path(file.filename or "document").name[:255],
        storage_key=storage_key,
        content_type=content_type,
        file_size=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
        status="processing",
    )
    # Flush first so the document receives its database-generated ID.
    # The document and outbox event are still committed atomically below.
    db.add(doc)
    await db.flush()

    event_id = str(uuid.uuid4())
    event_payload = {
        "event_id": event_id,
        "event_type": "document.ingestion.requested",
        "schema_version": 1,
        "document_id": str(doc.id),
        "workspace_id": str(workspace_id),
        "requested_by": str(user.id),
    }
    db.add(OutboxEvent(
        event_id=event_id,
        topic=settings.KAFKA_DOCUMENT_TOPIC,
        aggregate_id=doc.id,
        payload=event_payload,
    ))
    # Document and event are committed atomically.
    await db.commit()
    await db.refresh(doc)
    await cache_delete_pattern(f"documind:cache:documents:{workspace_id}:*")
    return doc
@router.get("/workspaces/{workspace_id}/documents", response_model=list[DocumentResponse])
async def list_documents(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(workspace_id, user, db)
    cache_key = f"documind:cache:documents:{workspace_id}:{user.id}"
    cached = await cache_get_json(cache_key)
    if cached is not None:
        return cached
    result = await db.scalars(
        select(Document)
        .where(Document.workspace_id == workspace_id)
        .order_by(Document.created_at.desc())
    )
    documents = jsonable_encoder(list(result.all()))
    await cache_set_json(cache_key, documents, ttl_seconds=15)
    return documents


@router.delete("/workspaces/{workspace_id}/documents/{document_id}", status_code=204)
async def delete_document(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await require_workspace(workspace_id, user, db)
    if membership.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewer role cannot delete documents")
    doc = await db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.workspace_id == workspace_id,
        )
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    path = _stored_path(workspace_id, doc.storage_key)
    await db.delete(doc)
    await db.commit()
    await cache_delete_pattern(f"documind:cache:documents:{workspace_id}:*")
    path.unlink(missing_ok=True)


# AUTOMATIC_EXACT_COUNT_ROUTING
def _count_document_pages(pages: list[tuple[int | None, str]], term: str) -> dict:
    """Single source of truth for whole-document and chat-triggered counting."""
    cleaned = term.strip()
    if not cleaned:
        raise ValueError("The search term cannot be empty.")

    if re.fullmatch(r"[\w'-]+", cleaned, flags=re.UNICODE):
        pattern = re.compile(rf"(?<![\w'-]){re.escape(cleaned)}(?![\w'-])", re.IGNORECASE)
        per_page = [
            {"page_number": page, "count": len(pattern.findall(text))}
            for page, text in pages
        ]
        mode = "whole_word_case_insensitive"
    else:
        folded = cleaned.casefold()
        per_page = [
            {"page_number": page, "count": text.casefold().count(folded)}
            for page, text in pages
        ]
        mode = "literal_substring_case_insensitive"

    return {
        "term": cleaned,
        "count": sum(item["count"] for item in per_page),
        "counting_mode": mode,
        "per_page": per_page,
    }


def _extract_count_term(question: str) -> str | None:
    """Recognize explicit frequency/count requests without routing explanations to counting."""
    q = re.sub(r"\s+", " ", question).strip().casefold()
    patterns = [
        r"\bhow many times\s+(?:does\s+)?(?:the\s+)?(?:word|term|phrase)?\s*['“\"]?(.+?)['”\"]?\s+(?:appear|appears|occur|occurs|is present|are present|is mentioned|are mentioned|is found|are found)\b",
        r"\bhow often\s+(?:is\s+)?(?:the\s+)?(?:word|term|phrase)?\s*['“\"]?(.+?)['”\"]?\s+(?:mentioned|appear|appears|occur|occurs|found|used)\b",
        r"\b(?:count occurrences of|find the count of|count)\s+(?:the\s+)?(?:word|term|phrase)?\s*['“\"]?(.+?)['”\"]?\s+(?:in|across|within|throughout)\s+(?:the\s+)?(?:entire\s+|whole\s+|full\s+)?document\b",
        r"\b(?:number of occurrences of|occurrences of)\s+(?:the\s+)?(?:word|term|phrase)?\s*['“\"]?(.+?)['”\"]?\s+(?:in|across|within|throughout)\s+(?:the\s+)?(?:entire\s+|whole\s+|full\s+)?document\b",
        r"\b(?:how many|count)\s+(?:occurrences|mentions|instances)\s+of\s+['“\"]?(.+?)['”\"]?(?:\s+are there|\s+in|\s+across|\s+within|\s+throughout|\?|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, q, flags=re.IGNORECASE)
        if match:
            term = match.group(1).strip().strip(" \t\r\n.,!?;:'\"“”‘’")
            if term and len(term) <= 100:
                return term
    return None

@router.get("/workspaces/{workspace_id}/documents/{document_id}/exact-count")
async def exact_document_count(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    term: str = Query(min_length=1, max_length=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Count a literal term across the entire source document, not retrieved chunks."""
    await require_workspace(workspace_id, user, db)
    doc = await db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.workspace_id == workspace_id,
        )
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    path = _stored_path(workspace_id, doc.storage_key)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Stored document file not found")
    try:
        pages, page_count = extract_text(path, doc.content_type)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not extract document text: {str(exc)[:200]}")
    counted = _count_document_pages(pages, term)
    return {
        "document_id": str(doc.id),
        "filename": doc.original_filename,
        "term": counted["term"],
        "count": counted["count"],
        "counting_mode": counted["counting_mode"],
        "page_count": page_count,
        "per_page": counted["per_page"],
    }


@router.post("/workspaces/{workspace_id}/chat", response_model=ChatResponse)
async def chat(
    workspace_id: uuid.UUID,
    payload: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(workspace_id, user, db)
    if payload.conversation_id:
        conversation = await db.scalar(
            select(Conversation).where(
                Conversation.id == payload.conversation_id,
                Conversation.workspace_id == workspace_id,
                Conversation.user_id == user.id,
            )
        )
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = Conversation(
            workspace_id=workspace_id,
            user_id=user.id,
            title=payload.question[:100],
        )
        db.add(conversation)
        await db.flush()

    count_term = _extract_count_term(payload.question)
    if payload.document_id:
        scoped_doc = await db.scalar(
            select(Document).where(
                Document.id == payload.document_id,
                Document.workspace_id == workspace_id,
                Document.status == "ready",
            )
        )
        if scoped_doc is None:
            raise HTTPException(status_code=404, detail="Selected document not found or not ready in this workspace.")

    if count_term:
        ready_docs = await db.scalars(
            select(Document)
            .where(
                Document.workspace_id == workspace_id,
                Document.status == "ready",
                *([Document.id == payload.document_id] if payload.document_id else []),
            )
            .order_by(Document.created_at.asc())
        )
        documents = list(ready_docs.all())
        if not documents:
            answer = "There are no ready documents in this workspace to count."
        else:
            results = []
            for doc in documents:
                path = _stored_path(workspace_id, doc.storage_key)
                if not path.is_file():
                    raise HTTPException(
                        status_code=404,
                        detail=f"Stored document file not found: {doc.original_filename}",
                    )
                try:
                    pages, _ = extract_text(path, doc.content_type)
                    counted = _count_document_pages(pages, count_term)
                except Exception as exc:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Could not count {doc.original_filename}: {str(exc)[:200]}",
                    )
                results.append((doc, counted))

            total = sum(item["count"] for _, item in results)
            mode = results[0][1]["counting_mode"]
            if len(results) == 1:
                doc, counted = results[0]
                unit = "occurrence" if counted["count"] == 1 else "occurrences"
                answer = (
                    f'The {mode.replace("_", " ")} count for "{count_term}" '
                    f'in {doc.original_filename} is {counted["count"]} {unit}. '
                    "This was calculated from the complete extracted document, "
                    "not from retrieved passages."
                )
            else:
                breakdown = "; ".join(
                    f'{doc.original_filename}: {counted["count"]}'
                    for doc, counted in results
                )
                answer = (
                    f'The total whole-document count for "{count_term}" across '
                    f'{len(results)} ready documents is {total}. Per-document counts: '
                    f'{breakdown}. Each document was scanned in full.'
                )

        db.add(Message(conversation_id=conversation.id, role="user", content=payload.question))
        db.add(
            Message(
                conversation_id=conversation.id,
                role="assistant",
                content=answer,
                citations_json="[]",
            )
        )
        await db.commit()
        return ChatResponse(
            conversation_id=conversation.id,
            answer=answer,
            citations=[],
        )

    retrieval_started = time.perf_counter()
    query_vector = (await embed_texts([payload.question]))[0]
    semantic_distance = DocumentChunk.embedding.cosine_distance(query_vector)
    keyword_rank = func.ts_rank_cd(
        func.to_tsvector("english", DocumentChunk.content),
        func.plainto_tsquery("english", payload.question),
    )
    base_filter = (
        DocumentChunk.workspace_id == workspace_id,
        Document.status == "ready",
        *([DocumentChunk.document_id == payload.document_id] if payload.document_id else []),
    )

    # Fetch independent semantic and lexical candidate sets, then fuse ranks in Python.
    semantic_result = await db.execute(
        select(DocumentChunk, Document.original_filename, semantic_distance.label("distance"))
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(*base_filter)
        .order_by(semantic_distance)
        .limit(max(settings.RETRIEVAL_TOP_K * 4, 20))
    )
    keyword_result = await db.execute(
        select(DocumentChunk, Document.original_filename, keyword_rank.label("keyword_score"))
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            *base_filter,
            func.to_tsvector("english", DocumentChunk.content).op("@@")(
                func.plainto_tsquery("english", payload.question)
            ),
        )
        .order_by(keyword_rank.desc())
        .limit(max(settings.RETRIEVAL_TOP_K * 4, 20))
    )

    candidates: dict[uuid.UUID, dict] = {}
    for chunk, filename, distance in semantic_result.all():
        candidates[chunk.id] = {
            "chunk": chunk,
            "filename": filename,
            "semantic": max(0.0, min(1.0, 1.0 - float(distance))),
            "keyword": 0.0,
        }
    max_keyword = max(
        (float(row.keyword_score or 0.0) for row in keyword_result.all()),
        default=0.0,
    )
    # Re-run the small lexical query to preserve rows after computing its normalizer.
    keyword_rows = await db.execute(
        select(DocumentChunk, Document.original_filename, keyword_rank.label("keyword_score"))
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            *base_filter,
            func.to_tsvector("english", DocumentChunk.content).op("@@")(
                func.plainto_tsquery("english", payload.question)
            ),
        )
        .order_by(keyword_rank.desc())
        .limit(max(settings.RETRIEVAL_TOP_K * 4, 20))
    )
    for chunk, filename, rank in keyword_rows.all():
        item = candidates.setdefault(
            chunk.id,
            {"chunk": chunk, "filename": filename, "semantic": 0.0, "keyword": 0.0},
        )
        item["keyword"] = (
            min(1.0, float(rank or 0.0) / max_keyword) if max_keyword > 0 else 0.0
        )

    ranked = []
    seen_content = set()
    for item in candidates.values():
        chunk = item["chunk"]
        normalized = re.sub(r"\W+", " ", chunk.content.casefold()).strip()
        if not normalized or normalized in seen_content:
            continue
        seen_content.add(normalized)
        item["score"] = 0.75 * item["semantic"] + 0.25 * item["keyword"]
        if item["score"] >= 0.12:
            ranked.append(item)
    ranked.sort(key=lambda item: item["score"], reverse=True)
    selected = ranked[: settings.RETRIEVAL_TOP_K]
    await add_metric('rag.retrieval.calls', 1)
    await add_metric('rag.retrieval.candidates_total', len(candidates))
    await add_metric('rag.retrieval.selected_total', len(selected))
    await add_metric('rag.retrieval.latency_ms_total', (time.perf_counter() - retrieval_started) * 1000)
    if not selected:
        await add_metric('rag.retrieval.empty_results', 1)

    citations = []
    context_lines = []
    for number, item in enumerate(selected, 1):
        chunk = item["chunk"]
        citations.append(
            Citation(
                document_id=chunk.document_id,
                filename=item["filename"],
                chunk_id=chunk.id,
                page_number=chunk.page_number,
                excerpt=chunk.content[:700],
                score=round(item["score"], 4),
            )
        )
        page = f", page {chunk.page_number}" if chunk.page_number else ""
        context_lines.append(
            f"[{number}] {item['filename']}{page}: {chunk.content}"
        )

    if context_lines:
        generation_started = time.perf_counter()
        answer = await generate_answer(payload.question, "\n\n".join(context_lines))
        await add_metric('rag.answers.generated', 1)
        await add_metric('rag.answer.generation_ms_total', (time.perf_counter() - generation_started) * 1000)
        await add_metric('rag.answer.citations_total', len(citations))
    else:
        answer = (
            "I couldn't find sufficiently relevant passages in this workspace's "
            "indexed documents to answer that question. Try a more specific question "
            "or check that the relevant document has status 'ready'."
        )

    db.add(Message(conversation_id=conversation.id, role="user", content=payload.question))
    db.add(
        Message(
            conversation_id=conversation.id,
            role="assistant",
            content=answer,
            citations_json=json.dumps([c.model_dump(mode="json") for c in citations]),
        )
    )
    await db.commit()
    return ChatResponse(
        conversation_id=conversation.id,
        answer=answer,
        citations=citations,
    )


@router.get("/workspaces/{workspace_id}/conversations")
async def list_conversations(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(workspace_id, user, db)
    rows = await db.scalars(
        select(Conversation)
        .where(
            Conversation.workspace_id == workspace_id,
            Conversation.user_id == user.id,
        )
        .order_by(Conversation.updated_at.desc())
    )
    return [
        {"id": str(c.id), "title": c.title, "created_at": c.created_at}
        for c in rows.all()
    ]


@router.get("/workspaces/{workspace_id}/conversations/{conversation_id}/messages")
async def list_messages(
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace(workspace_id, user, db)
    conversation = await db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.workspace_id == workspace_id,
            Conversation.user_id == user.id,
        )
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    rows = await db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
    )
    return [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "citations": json.loads(m.citations_json),
            "created_at": m.created_at,
        }
        for m in rows.all()
    ]


@router.post(
    "/workspaces/{workspace_id}/documents/{document_id}/reindex",
    response_model=DocumentResponse,
)
async def reindex_document(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await require_workspace(workspace_id, user, db)
    if membership.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewer role cannot re-index documents")
    doc = await db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.workspace_id == workspace_id,
        )
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    path = _stored_path(workspace_id, doc.storage_key)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Stored document file not found")

    try:
        pages, page_count = extract_text(path, doc.content_type)
        chunks = chunk_pages(pages)
        if not chunks:
            raise ValueError("No extractable text was found.")
        vectors = await embed_texts([part for _, _, part in chunks])
        if len(vectors) != len(chunks):
            raise ValueError("Embedding count does not match chunk count.")
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Re-indexing failed; existing chunks preserved: {str(exc)[:300]}",
        )

    await db.execute(
        delete(DocumentChunk).where(
            DocumentChunk.document_id == doc.id,
            DocumentChunk.workspace_id == workspace_id,
        )
    )
    for (index, page, content), vector in zip(chunks, vectors):
        db.add(
            DocumentChunk(
                document_id=doc.id,
                workspace_id=workspace_id,
                chunk_index=index,
                page_number=page,
                content=content,
                embedding=vector,
            )
        )
    doc.page_count = page_count
    doc.chunk_count = len(chunks)
    doc.status = "ready"
    doc.error_message = None
    await db.commit()
    await db.refresh(doc)
    await cache_delete_pattern(f"documind:cache:documents:{workspace_id}:*")
    return doc
