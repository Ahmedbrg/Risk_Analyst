from fastapi import APIRouter, UploadFile, File, HTTPException
from app.schemas.document import DocumentUploadResponse, RAGQueryResult
from app.services.rag_service import rag_service

router = APIRouter()

# Max file size: 15 MB
MAX_FILE_SIZE = 15 * 1024 * 1024


@router.post("/documents/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(file: UploadFile = File(...)) -> DocumentUploadResponse:
    """Upload a PDF, DOCX, or TXT file for RAG analysis."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 15MB)")

    return rag_service.process_and_index_document(file.filename, contents)


@router.post("/documents/query", response_model=RAGQueryResult)
async def query_documents(query: str, top_k: int = 3) -> RAGQueryResult:
    """Search uploaded documents for relevant context."""
    return rag_service.retrieve_relevant_context(query, top_k=top_k)
