from app.services.rag_service import rag_service


def test_document_indexing_and_query():
    """Should index a document and retrieve relevant chunks."""
    sample_text = "Section 4.2 Liability: Total liability is capped at $50,000. Notice period is 30 days."
    result = rag_service.process_and_index_document("test_agreement.txt", sample_text.encode("utf-8"))

    assert result.chunks_created >= 1
    assert result.filename == "test_agreement.txt"

    # Query should find the relevant chunk
    query_result = rag_service.retrieve_relevant_context("What is the liability cap?")
    assert len(query_result.retrieved_chunks) >= 1
    assert query_result.retrieved_chunks[0].filename == "test_agreement.txt"
