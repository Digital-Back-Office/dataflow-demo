"""
Benchmark upload/index pipeline performance for legal-doc summarizer.

Usage:
  python scripts/benchmark_pipeline.py --files uploads/sample.pdf
  python scripts/benchmark_pipeline.py --files uploads/a.pdf uploads/b.pdf --output data/benchmark_results.json
"""

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from statistics import mean
from typing import List

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
for sub in ("docs_ingestion", "rag_pipeline"):
    sub_path = os.path.join(PROJECT_ROOT, sub)
    if sub_path not in sys.path:
        sys.path.insert(0, sub_path)

from doc_loader import DocumentLoader
from clean_text import TextCleaner
from chunk_docs import DocChunker
from embeddings import EmbeddingModel
from vector_store import VectorStore


@dataclass
class FileBenchmark:
    file: str
    size_mb: float
    pages: int
    words: int
    chunk_size: int
    chunk_overlap: int
    chunks: int
    load_s: float
    clean_s: float
    chunk_s: float
    embed_s: float
    index_s: float
    total_s: float


def choose_chunk_settings(total_pages: int) -> tuple[int, int]:
    if total_pages <= 40:
        return 500, 50
    return 800, 80


def benchmark_file(file_path: str, data_dir: str) -> FileBenchmark:
    loader = DocumentLoader()
    cleaner = TextCleaner()
    embedder = EmbeddingModel(data_dir=data_dir)
    store = VectorStore(data_dir=data_dir, collection_name=f"bench_{int(time.time() * 1000)}")

    t0 = time.perf_counter()
    doc = loader.load_file(file_path)
    load_s = time.perf_counter() - t0
    if doc is None:
        raise RuntimeError(f"Could not parse file: {file_path}")

    pages = doc.get("total_pages", 1)
    size_mb = os.path.getsize(file_path) / (1024 * 1024)

    t1 = time.perf_counter()
    cleaned = cleaner.clean_document(doc)
    clean_s = time.perf_counter() - t1
    cleaned["pages"] = doc.get("pages", [])
    cleaned["total_pages"] = pages

    chunk_size, chunk_overlap = choose_chunk_settings(pages)
    chunker = DocChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap, output_dir=data_dir)

    t2 = time.perf_counter()
    chunks = chunker.chunk_document(cleaned)
    chunk_s = time.perf_counter() - t2

    t3 = time.perf_counter()
    embeddings = embedder.embed_chunks(chunks)
    embed_s = time.perf_counter() - t3

    t4 = time.perf_counter()
    store.add_document_chunks(embeddings, chunks)
    index_s = time.perf_counter() - t4

    text = cleaned.get("content", "")
    words = len(text.split())
    total_s = load_s + clean_s + chunk_s + embed_s + index_s

    return FileBenchmark(
        file=os.path.basename(file_path),
        size_mb=size_mb,
        pages=pages,
        words=words,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        chunks=len(chunks),
        load_s=load_s,
        clean_s=clean_s,
        chunk_s=chunk_s,
        embed_s=embed_s,
        index_s=index_s,
        total_s=total_s,
    )


def print_table(results: List[FileBenchmark]) -> None:
    print("\n=== Pipeline Benchmark Results ===")
    for r in results:
        print(
            f"- {r.file}: {r.pages} pages | {r.size_mb:.2f} MB | {r.chunks} chunks | "
            f"total {r.total_s:.2f}s (load {r.load_s:.2f}s, clean {r.clean_s:.2f}s, "
            f"chunk {r.chunk_s:.2f}s, embed {r.embed_s:.2f}s, index {r.index_s:.2f}s)"
        )

    by_page = [r.total_s / max(r.pages, 1) for r in results]
    by_chunk = [r.total_s / max(r.chunks, 1) for r in results]
    print("\n--- Aggregate ---")
    print(f"avg sec/page: {mean(by_page):.3f}")
    print(f"avg sec/chunk: {mean(by_chunk):.3f}")


def main():
    parser = argparse.ArgumentParser(description="Benchmark document processing + indexing pipeline.")
    parser.add_argument("--files", nargs="+", required=True, help="Input files to benchmark")
    parser.add_argument("--data-dir", default="data/benchmarks", help="Output folder for benchmark artifacts")
    parser.add_argument("--output", default="", help="Optional JSON output path")
    args = parser.parse_args()

    os.makedirs(args.data_dir, exist_ok=True)

    results: List[FileBenchmark] = []
    for fp in args.files:
        if not os.path.exists(fp):
            raise FileNotFoundError(fp)
        results.append(benchmark_file(fp, data_dir=args.data_dir))

    print_table(results)

    if args.output:
        payload = [asdict(r) for r in results]
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"\nSaved benchmark JSON: {args.output}")


if __name__ == "__main__":
    main()
