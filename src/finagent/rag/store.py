"""RAG vector store + embedding helpers (ChromaDB).

Heavy/network deps (chromadb, voyageai, openai) are imported lazily so importing this
module never fails in a minimal install — only *calling* into a backend that isn't
present raises. Chunking is pure Python and unit-tested.
"""

from __future__ import annotations

from ..config import get_settings

COLLECTION_NAME = "filings"


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping word windows (~``chunk_size`` words each).

    Word windows approximate token windows closely enough for retrieval and keep the
    function dependency-free and deterministic (so it can be unit-tested).
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and < chunk_size")
    words = text.split()
    if not words:
        return []
    step = chunk_size - overlap
    chunks: list[str] = []
    for start in range(0, len(words), step):
        window = words[start : start + chunk_size]
        if window:
            chunks.append(" ".join(window))
        if start + chunk_size >= len(words):
            break
    return chunks


def embed_texts(texts: list[str], *, input_type: str = "document") -> list[list[float]]:
    """Embed texts with the configured provider (voyage | openai)."""
    s = get_settings()
    provider = s.embedding_provider
    if provider == "voyage":
        import voyageai

        if not s.voyage_api_key:
            raise RuntimeError("EMBEDDING_PROVIDER=voyage but VOYAGE_API_KEY is empty.")
        client = voyageai.Client(api_key=s.voyage_api_key)
        result = client.embed(texts, model=s.voyage_model, input_type=input_type)
        return result.embeddings
    if provider == "openai":
        from openai import OpenAI

        if not s.openai_api_key:
            raise RuntimeError("EMBEDDING_PROVIDER=openai but OPENAI_API_KEY is empty.")
        client = OpenAI(api_key=s.openai_api_key)
        resp = client.embeddings.create(model=s.openai_embedding_model, input=texts)
        return [d.embedding for d in resp.data]
    raise ValueError(f"Unknown EMBEDDING_PROVIDER '{provider}' (use voyage|openai).")


def get_collection(persist_dir: str | None = None):
    """Return the persistent Chroma collection (created if missing)."""
    import chromadb

    s = get_settings()
    path = persist_dir or str(s.project_root / s.chroma_dir)
    client = chromadb.PersistentClient(path=path)
    # We pass our own embeddings on add/query, so no embedding_function is set here.
    return client.get_or_create_collection(name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
