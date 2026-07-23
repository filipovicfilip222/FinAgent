"""Ingest sample filing PDFs into the ChromaDB store.

Run locally (needs the ``rag`` extra + an embedding key):

    python -m finagent.rag.ingest            # ingest data/sample_filings/*.pdf
    python -m finagent.rag.ingest --reset    # wipe the collection first

Each PDF is read, chunked (~500-word windows, 50 overlap), embedded and written with
metadata (company, filing_type, source file, chunk index) that becomes the citation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..config import get_settings
from .store import chunk_text, embed_texts, get_collection


def read_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _infer_metadata(path: Path) -> dict:
    """Best-effort metadata from a filename like ``AAPL_10-K_2025.pdf``."""
    stem = path.stem
    parts = stem.split("_")
    company = parts[0] if parts else stem
    filing_type = parts[1] if len(parts) > 1 else "unknown"
    date = parts[2] if len(parts) > 2 else "unknown"
    return {"company": company, "filing_type": filing_type, "date": date, "source_file": path.name}


def ingest_filings(data_dir: str | None = None, *, reset: bool = False) -> dict:
    s = get_settings()
    folder = Path(data_dir) if data_dir else (s.project_root / "data" / "sample_filings")
    pdfs = sorted(folder.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"No PDFs found in {folder}")

    collection = get_collection()
    if reset:
        # Clear existing docs (delete-by-empty-where matches all).
        existing = collection.get()
        if existing.get("ids"):
            collection.delete(ids=existing["ids"])

    total_chunks = 0
    per_file = {}
    for pdf in pdfs:
        text = read_pdf(pdf)
        chunks = chunk_text(text)
        if not chunks:
            per_file[pdf.name] = 0
            continue
        meta = _infer_metadata(pdf)
        embeddings = embed_texts(chunks, input_type="document")
        ids = [f"{pdf.stem}::chunk::{i}" for i in range(len(chunks))]
        metadatas = [{**meta, "chunk_index": i} for i in range(len(chunks))]
        collection.add(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metadatas)
        per_file[pdf.name] = len(chunks)
        total_chunks += len(chunks)

    return {"files": len(pdfs), "chunks": total_chunks, "per_file": per_file}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ingest sample filings into ChromaDB.")
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args(argv)
    stats = ingest_filings(args.data_dir, reset=args.reset)
    print(f"Ingested {stats['chunks']} chunks from {stats['files']} file(s):")
    for name, n in stats["per_file"].items():
        print(f"  {name}: {n} chunks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
