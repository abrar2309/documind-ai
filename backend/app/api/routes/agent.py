import json
import asyncio
import logging
import uuid
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.database.session import get_db
from app.models.conversation import Conversation, Message
from app.models.membership import WorkspaceMembership
from app.models.user import User
from app.services.agent_tools import run_agent
from app.core.observability import add_metric

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Bounded AI Agent"])
AGENT_SEMAPHORE = asyncio.Semaphore(max(1, settings.AGENT_MAX_CONCURRENT))


class AgentRequest(BaseModel):
    task: str = Field(min_length=3, max_length=8000)
    conversation_id: uuid.UUID | None = None


@router.post("/workspaces/{workspace_id}/agent")
async def run_workspace_agent(
    workspace_id: uuid.UUID,
    payload: AgentRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await db.scalar(select(WorkspaceMembership).where(
        WorkspaceMembership.workspace_id == workspace_id,
        WorkspaceMembership.user_id == user.id,
    ))
    if membership is None:
        raise HTTPException(status_code=403, detail="Workspace membership required")

    if payload.conversation_id:
        conversation = await db.scalar(select(Conversation).where(
            Conversation.id == payload.conversation_id,
            Conversation.workspace_id == workspace_id,
            Conversation.user_id == user.id,
        ))
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = Conversation(
            workspace_id=workspace_id,
            user_id=user.id,
            title=("Agent: " + payload.task[:90]),
        )
        db.add(conversation)
        await db.flush()

    acquired = False
    agent_started = time.perf_counter()
    try:
        try:
            await asyncio.wait_for(AGENT_SEMAPHORE.acquire(), timeout=0.05)
            acquired = True
        except asyncio.TimeoutError:
            await add_metric("agent.capacity_rejected", 1)
            raise HTTPException(status_code=429, detail="Agent capacity is busy. Retry shortly.", headers={"Retry-After": "2"})
        result = await run_agent(payload.task, db, workspace_id, user.id)
        await add_metric('agent.requests.completed', 1)
        await add_metric('agent.execution_ms_total', (time.perf_counter() - agent_started) * 1000)
        await add_metric('agent.steps_total', len(result.get('steps') or []))
    except ValueError as exc:
        await add_metric('agent.requests.rejected', 1)
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        await db.rollback()
        raise
    except Exception as exc:
        await add_metric('agent.requests.failed', 1)
        logger.exception("Agent execution failed for workspace %s", workspace_id)
        await db.rollback()
        # Do not leak internal URLs, credentials, or stack traces to API clients.
        raise HTTPException(status_code=502, detail="Agent execution failed. Check backend logs.")
    finally:
        if acquired:
            AGENT_SEMAPHORE.release()

    db.add(Message(
        conversation_id=conversation.id,
        role="user",
        content=payload.task,
    ))
    db.add(Message(
        conversation_id=conversation.id,
        role="assistant",
        content=result["answer"],
        citations_json="[]",
    ))
    await db.commit()
    return {
        "conversation_id": str(conversation.id),
        "answer": result["answer"],
        "steps": result["steps"],
        "max_steps": result["max_steps"],
    }
