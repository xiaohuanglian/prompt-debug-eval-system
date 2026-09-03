from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

_WORD = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+")

def _tokenize(text: str) -> List[str]:
    return [m.group(0).lower() for m in _WORD.finditer(text or "")]

@dataclass
class DocChunk:
    doc_id: str
    path: str
    title: str
    content: str

class NaiveKeywordRetriever:
    """Naive keyword overlap retriever as a vector-RAG placeholder."""

    def __init__(self, define_dir: Optional[str] = None):
        self.define_dir = define_dir
        self.chunks: List[DocChunk] = []
        if define_dir:
            self.chunks = self._load_chunks(define_dir)

    def _load_chunks(self, define_dir: str) -> List[DocChunk]:
        chunks: List[DocChunk] = []
        md_files: List[str] = []
        for r, _, files in os.walk(define_dir):
            for fn in files:
                if fn.lower().endswith(".md"):
                    md_files.append(os.path.join(r, fn))

        for p in sorted(md_files):
            try:
                txt = open(p, "r", encoding="utf-8").read()
            except Exception:
                continue

            parts: List[Tuple[str, str]] = []
            current_title = os.path.basename(p)
            buf: List[str] = []
            for line in txt.splitlines():
                if line.startswith("#"):
                    if buf:
                        parts.append((current_title, "\n".join(buf).strip()))
                        buf = []
                    current_title = line.strip()
                else:
                    buf.append(line)
            if buf:
                parts.append((current_title, "\n".join(buf).strip()))

            for i, (title, content) in enumerate(parts):
                if not content:
                    continue
                doc_id = f"{os.path.relpath(p, define_dir)}::{i}"
                chunks.append(DocChunk(doc_id=doc_id, path=p, title=title, content=content))
        return chunks

    def retrieve(self, query: str, top_k: int = 6) -> List[Tuple[DocChunk, float]]:
        if not self.chunks:
            return []
        qtok = set(_tokenize(query))
        if not qtok:
            return []
        scored: List[Tuple[DocChunk, float]] = []
        for ch in self.chunks:
            ctok = set(_tokenize(ch.title + "\n" + ch.content))
            overlap = len(qtok & ctok)
            if overlap:
                scored.append((ch, overlap / max(1, len(qtok))))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
