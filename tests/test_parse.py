from pathlib import Path

import pymupdf
from fastapi.testclient import TestClient

from app.ingestion.extract import batches, terme_normalise
from app.ingestion.parse_pdf import parse
from app.main import app

BODY = "Le présent texte décrit les garanties offertes à l'assuré dans le cadre du contrat. "


def make_pdf(path: Path) -> None:
    """Synthetic CG: running header, numbered 13 pt headings, 10 pt body, page numbers."""
    doc = pymupdf.open()
    sections = [("1.", "Lexique"), ("1.1.", "Effraction"), ("2.", "Garantie vol"), ("2.1.", "Exclusions")]
    for i, (num, title) in enumerate(sections * 5):
        page = doc.new_page()
        page.insert_text((50, 30), "CONDITIONS GÉNÉRALES – HABITATION", fontsize=8)
        page.insert_text((50, 80), num, fontsize=13)
        page.insert_text((50, 100), f"{title} {i}", fontsize=13)
        y = 130
        for _ in range(6):
            page.insert_text((50, y), BODY[:80], fontsize=10)
            y += 14
        page.insert_text((300, 820), str(i + 1), fontsize=8)
    doc.save(path)


def test_parse_synthetic(tmp_path: Path) -> None:
    pdf = tmp_path / "cg.pdf"
    make_pdf(pdf)
    clauses = parse(pdf)
    assert len(clauses) == 20
    assert all(c.texte.strip() for c in clauses)
    assert not any("CONDITIONS GÉNÉRALES" in c.texte for c in clauses)  # running header removed
    assert clauses[1].numero == "1.1" and clauses[1].chemin.startswith("1. Lexique 0 > 1.1. Effraction")
    assert clauses[0].bboxes and clauses[0].bboxes[0][0] == 1


def test_batches_and_normalisation() -> None:
    clauses = [{"texte": "x" * 15_000, "chemin": ""} for _ in range(4)]
    assert [len(b) for b in batches(clauses)] == [2, 2]
    assert terme_normalise("Dépendances :") == "dependances"


def test_health() -> None:
    assert TestClient(app).get("/health").json() == {"status": "ok"}
