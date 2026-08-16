"""
AI Risk Analyst — Document & Chunk Schemas with Hierarchical Metadata.
"""

from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    document_id: str
    filename: str
    file_type: str
    size_bytes: int
    upload_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    page_count: Optional[int] = 1
    section_count: Optional[int] = 1


class DocumentChunk(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    page_number: int = 1
    section_title: str = "General"
    paragraph_index: int = 1
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    relevance_score: Optional[float] = None


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    file_type: str
    chunks_created: int
    message: str


class RAGQueryResult(BaseModel):
    query: str
    retrieved_chunks: List[DocumentChunk]
    grounded_context: str
    search_type: str = "Hybrid (Semantic Vector + BM25 Keyword Matching)"
