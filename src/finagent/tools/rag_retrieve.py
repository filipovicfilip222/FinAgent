"""RAG retrieval tool — top-k passages from indexed filing PDFs.

Runs against the ChromaDB collection built by ``finagent.rag.ingest``. Embedding /
vector-store deps are imported lazily (via ``rag.store``), so a call degrades to a
clear error when the ``rag`` extra isn't installed rather than breaking import.
"""

from __future__ import annotations

from ..rag.store import embed_texts, get_collection
from . import register


def _format_hit(doc: str, meta: dict, distance: float | None) -> str:
    company = meta.get("company", "?")
    ftype = meta.get("filing_type", "?")
    date = meta.get("date", "?")
    src = meta.get("source_file", "?")
    idx = meta.get("chunk_index", "?")
    snippet = doc.strip().replace("\n", " ")
    if len(snippet) > 500:
        snippet = snippet[:500] + " …"
    score = f", score={1 - distance:.3f}" if distance is not None else ""
    return f"[{company} {ftype} {date} · {src}#chunk{idx}{score}]\n{snippet}"


def rag_retrieve(tool_input: dict) -> str:
    query = str(tool_input.get("query", "")).strip()
    if not query:
        return "rag_retrieve requires a non-empty 'query'."
    k = int(tool_input.get("k", 4) or 4)

    collection = get_collection()
    if collection.count() == 0:
        return (
            "The filings index is empty. Run `python -m finagent.rag.ingest` first "
            "(requires the `rag` extra and an embedding key)."
        )

    query_emb = embed_texts([query], input_type="query")[0]
    res = collection.query(query_embeddings=[query_emb], n_results=k)
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[None] * len(docs)])[0]
    if not docs:
        return f"No passages retrieved for query: {query!r}"

    blocks = [
        _format_hit(d, m or {}, dist) for d, m, dist in zip(docs, metas, dists, strict=False)
    ]
    return f"Top {len(blocks)} passages for {query!r}:\n\n" + "\n\n".join(blocks)


register("rag_retrieve")(rag_retrieve)
