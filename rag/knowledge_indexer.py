"""
ClinIQ - Knowledge Indexer (Phase 5 - RAG)
=============================================
Indexes medical_knowledge.txt into ChromaDB using
sentence-transformers (all-MiniLM-L6-v2) embeddings.
"""

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CHROMA_DIR = os.environ.get("CHROMA_PERSIST_DIR", "./chroma_db")
COLLECTION_NAME = "medical_knowledge"


def _get_embedding_function():
    """Get the sentence-transformer embedding function for ChromaDB."""
    from chromadb.utils import embedding_functions
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )


def _get_client():
    """Get or create a persistent ChromaDB client."""
    import chromadb
    return chromadb.PersistentClient(path=CHROMA_DIR)


def index_knowledge_base(file_path: str = "data/medical_knowledge.txt") -> int:
    """
    Index the medical knowledge base into ChromaDB.
    Splits by '---' separator (each section = one topic).
    Returns number of chunks indexed.
    """
    file_path = str(Path(file_path).resolve())
    if not os.path.exists(file_path):
        logger.error(f"Knowledge base file not found: {file_path}")
        return 0

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Split into chunks by separator
    chunks = [c.strip() for c in content.split("---") if c.strip() and len(c.strip()) > 20]

    if not chunks:
        logger.warning("No valid chunks found in knowledge base")
        return 0

    client = _get_client()
    ef = _get_embedding_function()

    # Delete existing collection if any, to re-index fresh
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME, embedding_function=ef
    )

    # Prepare data
    ids = [f"med_kb_{i}" for i in range(len(chunks))]
    metadatas = []
    for i, chunk in enumerate(chunks):
        first_line = chunk.split("\n")[0].strip()
        metadatas.append({
            "source": "medical_knowledge.txt",
            "topic": first_line[:100],
            "chunk_index": i,
        })

    # Add in batches of 50
    batch_size = 50
    for start in range(0, len(chunks), batch_size):
        end = min(start + batch_size, len(chunks))
        collection.add(
            documents=chunks[start:end],
            metadatas=metadatas[start:end],
            ids=ids[start:end],
        )

    logger.info(f"Indexed {len(chunks)} chunks into ChromaDB collection '{COLLECTION_NAME}'")
    return len(chunks)


def is_indexed() -> bool:
    """Check if the knowledge base has already been indexed."""
    try:
        client = _get_client()
        collection = client.get_collection(
            name=COLLECTION_NAME, embedding_function=_get_embedding_function()
        )
        return collection.count() > 0
    except Exception:
        return False
