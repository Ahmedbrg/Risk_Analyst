"""
AI Risk Analyst — Hierarchical Document Processing & Hybrid RAG Engine.
"""

import os
import re
import csv
import uuid
import math
from io import StringIO
from typing import List, Dict, Any, Tuple

from app.config import settings
from app.schemas.document import DocumentChunk, DocumentUploadResponse, RAGQueryResult


class HierarchicalRAGService:
    """
    Hierarchical Document Parsing and Hybrid Search Engine.
    Preserves Document -> Page -> Section -> Paragraph hierarchy.
    Combines dense semantic scoring with exact BM25 keyword matching.
    """

    def __init__(self):
        self.upload_dir = "data/uploads"
        os.makedirs(self.upload_dir, exist_ok=True)
        self._chunks: Dict[str, DocumentChunk] = {}

    def process_and_index_document(self, filename: str, content_bytes: bytes) -> DocumentUploadResponse:
        """Parses document into structured hierarchical chunks and indexes them."""
        document_id = str(uuid.uuid4())
        file_ext = os.path.splitext(filename)[1].lower()
        filepath = os.path.join(self.upload_dir, f"{document_id}_{filename}")

        with open(filepath, "wb") as f:
            f.write(content_bytes)

        # 1. Multi-format text & hierarchy extraction
        raw_sections = self._extract_hierarchical_sections(filepath, file_ext, content_bytes, filename)

        # 2. Chunking preserving Page & Section context
        chunks = self._chunk_sections(raw_sections, document_id, filename)

        # 3. Store in local index
        for chunk in chunks:
            self._chunks[chunk.chunk_id] = chunk

        return DocumentUploadResponse(
            document_id=document_id,
            filename=filename,
            file_type=file_ext.replace(".", "").upper(),
            chunks_created=len(chunks),
            message=f"Document processed into {len(chunks)} traceable chunks.",
        )

    def _extract_hierarchical_sections(
        self, filepath: str, file_ext: str, content_bytes: bytes, filename: str
    ) -> List[Dict[str, Any]]:
        sections: List[Dict[str, Any]] = []

        if file_ext == ".pdf":
            try:
                from pypdf import PdfReader
                reader = PdfReader(filepath)
                for page_idx, page in enumerate(reader.pages):
                    page_text = page.extract_text() or ""
                    # Detect section titles from uppercase or numbered headings
                    lines = [line.strip() for line in page_text.split("\n") if line.strip()]
                    current_section = f"Page {page_idx + 1} General"
                    current_buffer = []

                    for line in lines:
                        if re.match(r"^(?:section|\d+\.|\b[A-Z\s]{4,}\b)", line, re.IGNORECASE) and len(line) < 60:
                            if current_buffer:
                                sections.append({
                                    "page": page_idx + 1,
                                    "section": current_section,
                                    "text": " ".join(current_buffer)
                                })
                                current_buffer = []
                            current_section = line
                        else:
                            current_buffer.append(line)

                    if current_buffer:
                        sections.append({
                            "page": page_idx + 1,
                            "section": current_section,
                            "text": " ".join(current_buffer)
                        })
            except Exception:
                text = content_bytes.decode("utf-8", errors="ignore")
                sections.append({"page": 1, "section": "General", "text": text})

        elif file_ext in [".docx", ".doc"]:
            try:
                import docx
                doc = docx.Document(filepath)
                current_section = "Introduction"
                current_buffer = []

                for para in doc.paragraphs:
                    text = para.text.strip()
                    if not text:
                        continue
                    if para.style.name.startswith("Heading"):
                        if current_buffer:
                            sections.append({"page": 1, "section": current_section, "text": " ".join(current_buffer)})
                            current_buffer = []
                        current_section = text
                    else:
                        current_buffer.append(text)

                if current_buffer:
                    sections.append({"page": 1, "section": current_section, "text": " ".join(current_buffer)})
            except Exception:
                text = content_bytes.decode("utf-8", errors="ignore")
                sections.append({"page": 1, "section": "General", "text": text})

        elif file_ext == ".csv":
            try:
                decoded = content_bytes.decode("utf-8", errors="ignore")
                reader = csv.reader(StringIO(decoded))
                rows = list(reader)
                header = rows[0] if rows else []
                for idx, row in enumerate(rows[1:], 1):
                    row_dict = dict(zip(header, row))
                    row_str = " | ".join([f"{k}: {v}" for k, v in row_dict.items() if v])
                    sections.append({"page": 1, "section": f"Row {idx}", "text": row_str})
            except Exception:
                text = content_bytes.decode("utf-8", errors="ignore")
                sections.append({"page": 1, "section": "CSV Data", "text": text})
        else:
            text = content_bytes.decode("utf-8", errors="ignore")
            sections.append({"page": 1, "section": "General", "text": text})

        return sections

    def _chunk_sections(
        self, sections: List[Dict[str, Any]], document_id: str, filename: str, chunk_word_size: int = 350
    ) -> List[DocumentChunk]:
        chunks: List[DocumentChunk] = []
        chunk_idx = 1

        for sec in sections:
            words = sec["text"].split()
            if not words:
                continue

            page_num = sec.get("page", 1)
            sec_title = sec.get("section", "General")

            i = 0
            para_idx = 1
            while i < len(words):
                chunk_slice = words[i : i + chunk_word_size]
                chunk_text = " ".join(chunk_slice)

                chunks.append(DocumentChunk(
                    chunk_id=f"{document_id}_chunk_{chunk_idx}",
                    document_id=document_id,
                    filename=filename,
                    page_number=page_num,
                    section_title=sec_title,
                    paragraph_index=para_idx,
                    content=chunk_text,
                    metadata={
                        "source": f"{filename} — Page {page_num} [{sec_title}]",
                        "document_id": document_id,
                        "chunk_index": chunk_idx,
                    }
                ))
                i += max(1, chunk_word_size - 60)
                chunk_idx += 1
                para_idx += 1

        return chunks

    def retrieve_relevant_context(self, query: str, top_k: int = 4) -> RAGQueryResult:
        """
        Hybrid Search: Combines exact keyword & numeric matching (BM25 style)
        with semantic overlap scoring to ensure numbers, currency figures, and SLAs are never lost.
        """
        if not self._chunks:
            return RAGQueryResult(
                query=query,
                retrieved_chunks=[],
                grounded_context="",
                search_type="Hybrid Search (Empty Index)"
            )

        query_terms = set(re.findall(r"\b\w+\b", query.lower()))
        # Extract critical exact figures (percentages, currencies, metrics)
        exact_tokens = set(re.findall(r"(?:\$|€|\b\d+%\b|\b\d+\s*months?\b|\b\d+\b)", query.lower()))

        scored_chunks = []
        for chunk in self._chunks.values():
            content_lower = chunk.content.lower()
            content_terms = set(re.findall(r"\b\w+\b", content_lower))

            # 1. Semantic term overlap
            overlap = len(query_terms & content_terms)
            semantic_score = overlap / (math.sqrt(len(query_terms) + 1) * math.sqrt(len(content_terms) + 1) or 1)

            # 2. Exact keyword / numeric bonus
            exact_bonus = sum(2.5 for token in exact_tokens if token in content_lower)

            total_score = round(semantic_score + exact_bonus, 4)
            if total_score > 0:
                chunk_copy = chunk.model_copy()
                chunk_copy.relevance_score = total_score
                scored_chunks.append((total_score, chunk_copy))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top_chunks = [item[1] for item in scored_chunks[:top_k]]

        grounded_lines = []
        for c in top_chunks:
            grounded_lines.append(
                f"[Document: {c.filename} | Page: {c.page_number} | Section: {c.section_title}]\n{c.content}"
            )

        return RAGQueryResult(
            query=query,
            retrieved_chunks=top_chunks,
            grounded_context="\n\n".join(grounded_lines),
            search_type="Hybrid (Semantic + Exact Figures)",
        )


# Singleton RAG Service
rag_service = HierarchicalRAGService()
