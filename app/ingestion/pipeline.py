from __future__ import annotations

import re


def split_text(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    if chunk_size <= 0:
        return [text]
    chunks: list[str] = []
    step = max(chunk_size - overlap, 1)
    for start in range(0, len(text), step):
        chunk = text[start : start + chunk_size]
        if chunk:
            chunks.append(chunk)
    return chunks


def split_paragraphs(text: str, target_chars: int = 1400, max_chars: int = 1800, min_chars: int = 600, overlap_chars: int = 0) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if not paragraphs:
        return split_text(text, max_chars, overlap_chars)

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(paragraph) > max_chars:
            chunks.extend(split_text(paragraph, target_chars, overlap_chars))
            current = ""
        else:
            current = paragraph
    if current:
        chunks.append(current)

    if min_chars > 0 and len(chunks) > 1:
        merged: list[str] = []
        for chunk in chunks:
            if merged and len(chunk) < min_chars:
                merged[-1] = f"{merged[-1]}\n\n{chunk}".strip()
            else:
                merged.append(chunk)
        chunks = merged
    return chunks

