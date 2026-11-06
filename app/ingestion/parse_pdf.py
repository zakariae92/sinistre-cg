"""PDF -> tree of clauses, each keeping the bounding boxes of its lines (for highlighting).

Generic over layouts: a heading is a line set in a larger font than the body text, or a short
bold line that does not end like a sentence. A numbering-only line ("1.12.") is merged with the
title that follows it. Running headers/footers (same text on many pages) and page numbers are
dropped.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

NUMERO = re.compile(r"^(?:(?:Article|Art\.?|Chapitre|Titre|Section)\s+)?(\d+(?:\.\d+)*|[IVX]+)\b[.)\-–]?\s*", re.I)
TOC_LINE = re.compile(r"\.{4,}|…{2,}|\s\d{1,3}$")
MAX_CHARS = 6000  # ~1 500 tokens
BULLETS = "◼▪●○•–-·​​"


@dataclass
class Line:
    page: int  # 1-based
    text: str
    size: float
    bold: bool
    bbox: tuple[float, float, float, float]


@dataclass
class Clause:
    numero: str | None
    titre: str
    chemin: str
    texte: str
    page_debut: int
    page_fin: int
    bboxes: list[list[float]] = field(default_factory=list)


def _norm(text: str) -> str:
    return re.sub(r"\d+", "#", text.strip().lower())


def read_lines(path: Path) -> list[Line]:
    doc = pymupdf.open(path)
    lines: list[Line] = []
    margins: set[tuple[int, str]] = set()  # (page, normalised text) of lines in the top/bottom 8 %
    for page in doc:  # type: ignore[attr-defined]
        page_lines: list[Line] = []
        height = page.rect.height
        for block in page.get_text("dict", sort=False)["blocks"]:
            for raw in block.get("lines", []):
                spans = [s for s in raw["spans"] if s["text"].strip()]
                if not spans:
                    continue
                text = " ".join("".join(s["text"] for s in spans).split()).strip(BULLETS + " ")
                if not text:
                    continue
                main = max(spans, key=lambda s: len(s["text"]))
                ln = Line(
                    page.number + 1,
                    text,
                    round(main["size"], 1),
                    bool(main["flags"] & 16) or "bold" in main["font"].lower(),
                    tuple(raw["bbox"]),
                )  # type: ignore[arg-type]
                page_lines.append(ln)
                if ln.bbox[1] < 0.08 * height or ln.bbox[3] > 0.92 * height:
                    margins.add((ln.page, _norm(text)))
        # Table of contents: dot leaders or most lines ending with a page number.
        toc = sum(bool(TOC_LINE.search(ln.text)) for ln in page_lines)
        if toc < max(5, len(page_lines) * 0.3):
            lines.extend(page_lines)
    # Running headers/footers: same margin text (digits aside) on more than a third of the pages.
    seen = Counter(t for _, t in margins)
    repeated = {t for t, n in seen.items() if n > max(3, doc.page_count / 3)}
    return [
        ln
        for ln in lines
        if not ln.text.isdigit()
        # a clause number ("1.12.") repeats by shape too: never treat it as a running header
        and (NUMERO.fullmatch(ln.text) or not ((ln.page, _norm(ln.text)) in margins and _norm(ln.text) in repeated))
    ]


def body_size(lines: list[Line]) -> float:
    weights: Counter[float] = Counter()
    for ln in lines:
        weights[ln.size] += len(ln.text)
    return weights.most_common(1)[0][0]


def is_heading(ln: Line, body: float) -> bool:
    if len(ln.text) > 140 or ln.size < body - 0.6:
        return False
    if ln.size >= body + 1.5:
        return True
    sentence_end = ln.text.endswith((".", ",", ";", ":")) and not NUMERO.fullmatch(ln.text)
    return ln.bold and not sentence_end and len(ln.text) < 100


def parse(path: Path) -> list[Clause]:
    lines = read_lines(path)
    body = body_size(lines)
    # Group consecutive heading lines (number + title, or a title wrapped on two lines).
    groups: list[tuple[bool, list[Line]]] = []
    for ln in lines:
        head = is_heading(ln, body)
        prev = groups[-1] if groups else None
        if prev and prev[0] == head and (not head or (ln.page == prev[1][-1].page and len(prev[1]) < 3)):
            groups[-1][1].append(ln)
        else:
            groups.append((head, [ln]))

    clauses: list[Clause] = []
    stack: list[tuple[float, int, str]] = []  # (size, numbering depth, title) of open headings
    title: str = "Préambule"
    numero: str | None = None
    heading_lines: list[Line] = []
    for head, group in groups:
        if head:
            text = " ".join(ln.text for ln in group)
            m = NUMERO.match(text)
            numero = m.group(1) if m and m.group(1) else None
            size = max(ln.size for ln in group)
            depth = numero.count(".") + 1 if numero and numero[0].isdigit() else 0
            while stack and (stack[-1][0] < size or (stack[-1][0] == size and stack[-1][1] >= depth)):
                stack.pop()
            stack.append((size, depth, text))
            title, heading_lines = text, group
            continue
        chemin = " > ".join(t for _, _, t in stack) or title
        body_text = "\n".join(ln.text for ln in group)
        all_lines = heading_lines + group
        # shortcut: split chunks share the bboxes of the whole clause; split lines too if highlights look too wide.
        for i, chunk in enumerate(_split(body_text)):
            clauses.append(
                Clause(
                    numero=f"{numero}#{i + 1}" if numero and i else numero,
                    titre=title,
                    chemin=chemin,
                    texte=chunk,
                    page_debut=all_lines[0].page,
                    page_fin=all_lines[-1].page,
                    bboxes=[[ln.page, *ln.bbox] for ln in all_lines],
                )
            )
        heading_lines = []
    return [c for c in clauses if len(c.texte) >= 20]


def _split(text: str) -> list[str]:
    if len(text) <= MAX_CHARS:
        return [text]
    chunks, current = [], ""
    for para in text.split("\n"):
        if current and len(current) + len(para) > MAX_CHARS:
            chunks.append(current)
            current = ""
        current += para + "\n"
    return [*chunks, current.strip()] if current.strip() else chunks
