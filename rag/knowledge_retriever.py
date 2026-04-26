"""
ClinIQ - Knowledge Retriever (Phase 5 - RAG)
===============================================
Queries ChromaDB for relevant medical context
to ground AI summaries in real clinical knowledge.
"""

import os
import logging
from typing import List
from schemas.medical_schemas import RetrievedContext

logger = logging.getLogger(__name__)

CHROMA_DIR = os.environ.get("CHROMA_PERSIST_DIR", "./chroma_db")
COLLECTION_NAME = "medical_knowledge"


def _get_embedding_function():
    from chromadb.utils import embedding_functions
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )


def _get_collection():
    import chromadb
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    ef = _get_embedding_function()
    return client.get_collection(name=COLLECTION_NAME, embedding_function=ef)


def retrieve_context(query: str, n_results: int = 3) -> List[RetrievedContext]:
    """
    Query ChromaDB for relevant medical knowledge passages.
    
    Args:
        query: Search query (e.g., "high glucose diabetes risk")
        n_results: Number of results to return
        
    Returns:
        List of RetrievedContext with text, source, and relevance score
    """
    try:
        collection = _get_collection()
        results = collection.query(query_texts=[query], n_results=n_results)
    except Exception as e:
        logger.error(f"RAG retrieval failed: {e}")
        return []

    contexts = []
    if results and results["documents"]:
        documents = results["documents"][0]
        distances = results["distances"][0] if results.get("distances") else [0] * len(documents)
        metadatas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(documents)

        for doc, dist, meta in zip(documents, distances, metadatas):
            # ChromaDB returns L2 distance; convert to similarity score (0-1)
            similarity = max(0, 1 - (dist / 2))
            source = meta.get("source", "medical_knowledge.txt")
            topic = meta.get("topic", "")

            contexts.append(RetrievedContext(
                text=doc,
                source=f"{source} - {topic}" if topic else source,
                relevance_score=round(similarity, 4),
            ))

    logger.info(f"Retrieved {len(contexts)} context passages for: '{query[:50]}...'")
    return contexts


def retrieve_for_abnormals(flagged_results) -> List[RetrievedContext]:
    """
    Retrieve RAG context for each abnormal finding.
    Builds targeted queries for better retrieval accuracy.
    """
    all_contexts = []
    seen_texts = set()

    for result in flagged_results:
        if result.status in ("NORMAL", "UNKNOWN"):
            continue

        # Build a targeted clinical query
        query = f"{result.test_name} {result.status.lower()} clinical significance"
        if result.status in ("HIGH", "CRITICAL_HIGH"):
            query += f" elevated {result.test_name} causes treatment"
        else:
            query += f" low {result.test_name} deficiency causes treatment"

        contexts = retrieve_context(query, n_results=2)
        for ctx in contexts:
            # Deduplicate across multiple abnormal findings
            text_key = ctx.text[:100]
            if text_key not in seen_texts:
                seen_texts.add(text_key)
                all_contexts.append(ctx)

    return all_contexts
