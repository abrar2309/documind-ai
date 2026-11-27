import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    workspace_id: uuid.UUID
    original_filename: str
    content_type: str
    file_size: int
    status: str
    error_message: str | None
    page_count: int
    chunk_count: int
    created_at: datetime

class Citation(BaseModel):
    document_id: uuid.UUID
    filename: str
    chunk_id: uuid.UUID
    page_number: int | None
    excerpt: str
    score: float

class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=8000)
    conversation_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None

class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    answer: str
    citations: list[Citation]
