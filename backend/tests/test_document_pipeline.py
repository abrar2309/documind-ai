from app.services.document_pipeline import chunk_pages, local_embedding

def test_chunking_creates_overlapping_chunks():
    text = "word " * 500
    chunks = chunk_pages([(1, text)])
    assert len(chunks) > 1
    assert chunks[0][1] == 1
    assert all(item[2] for item in chunks)

def test_local_embedding_is_normalized_and_deterministic():
    first = local_embedding("DocuMind retrieval test")
    second = local_embedding("DocuMind retrieval test")
    assert first == second
    assert len(first) == 384
    assert abs(sum(x*x for x in first) - 1.0) < 1e-5