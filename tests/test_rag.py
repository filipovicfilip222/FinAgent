"""RAG retrieval-tool logic, exercised with fakes.

The real embedding + Chroma calls are network/dep-gated (they run on the user's
machine), so here we inject a fake collection and a fake embedder to prove the
query -> embed -> search -> format flow deterministically.
"""

import finagent.tools.rag_retrieve as rr


class _FakeCollection:
    def __init__(self, n):
        self._n = n

    def count(self):
        return self._n

    def query(self, query_embeddings, n_results):
        docs = [
            "A substantial portion of the Company's manufacturing is performed by outsourcing "
            "partners located primarily in Asia, including China.",
            "The Company depends heavily on the iPhone and a decline in demand could affect revenue.",
        ][:n_results]
        metas = [
            {"company": "AAPL", "filing_type": "10-K", "date": "2025",
             "source_file": "AAPL_10-K_2025.pdf", "chunk_index": 1},
            {"company": "AAPL", "filing_type": "10-K", "date": "2025",
             "source_file": "AAPL_10-K_2025.pdf", "chunk_index": 2},
        ][:n_results]
        dists = [0.12, 0.31][:n_results]
        return {"documents": [docs], "metadatas": [metas], "distances": [dists]}


def test_rag_retrieve_formats_hits(monkeypatch):
    monkeypatch.setattr(rr, "get_collection", lambda: _FakeCollection(42))
    monkeypatch.setattr(rr, "embed_texts", lambda texts, input_type="query": [[0.1, 0.2, 0.3]])
    out = rr.rag_retrieve({"query": "What supply-chain risks does Apple cite?", "k": 2})
    assert "Top 2 passages" in out
    assert "outsourcing partners located primarily in Asia" in out
    assert "AAPL 10-K 2025" in out
    assert "score=" in out  # 1 - distance shown


def test_rag_retrieve_empty_index(monkeypatch):
    monkeypatch.setattr(rr, "get_collection", lambda: _FakeCollection(0))
    out = rr.rag_retrieve({"query": "anything", "k": 4})
    assert "index is empty" in out


def test_rag_retrieve_requires_query():
    assert "requires a non-empty" in rr.rag_retrieve({"query": "   "})
