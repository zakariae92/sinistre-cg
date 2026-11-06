"""Store a contract and its clauses (idempotent by sha256), with BGE-M3 embeddings."""

import json
import logging
from typing import Any

import httpx
import numpy as np

from app.config import get_settings
from app.db.session import connect
from app.ingestion.fetch import check_pdf, pdf_path
from app.ingestion.parse_pdf import parse

log = logging.getLogger(__name__)


def embed(texts: list[str]) -> list[np.ndarray]:
    out: list[np.ndarray] = []
    with httpx.Client(timeout=300) as client:
        for i in range(0, len(texts), 16):
            r = client.post(f"{get_settings().embeddings_url}/embed", json={"inputs": texts[i : i + 16], "truncate": True})
            r.raise_for_status()
            out += [np.array(v, dtype=np.float32) for v in r.json()]
    return out


def index_contract(source: dict[str, Any]) -> bool:
    """Returns False when the stored contract already has this sha256 (nothing to do)."""
    path = pdf_path(source)
    check = check_pdf(path)
    if check.statut != "ok":
        raise ValueError(f"{source['id']} : {check.raison}")
    with connect() as conn:
        row = conn.execute("SELECT sha256 FROM contracts WHERE id = %s", (source["id"],)).fetchone()
        if row and row["sha256"] == check.sha256:
            return False
        clauses = parse(path)
        vectors = embed([f"{source['assureur']} / {source['produit']} / {c.chemin}\n{c.texte}" for c in clauses])
        conn.execute("DELETE FROM contracts WHERE id = %s", (source["id"],))  # cascades to clauses + extraction
        conn.execute(
            """INSERT INTO contracts (id, assureur, produit, pays, cadre_legal, langue, version, source_url, sha256, nb_pages)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                source["id"],
                source["assureur"],
                source["produit"],
                source["pays"],
                source["cadre_legal"],
                source["langue"],
                str(source["version"]),
                source.get("source_page") or source["url"],
                check.sha256,
                check.pages,
            ),
        )
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO clauses
                   (id, contract_id, ordre, numero, titre, chemin, texte, page_debut, page_fin, bboxes, embedding)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                [
                    (
                        f"{source['id']}:{i}",
                        source["id"],
                        i,
                        c.numero,
                        c.titre,
                        c.chemin,
                        c.texte,
                        c.page_debut,
                        c.page_fin,
                        json.dumps(c.bboxes),
                        v,
                    )
                    for i, (c, v) in enumerate(zip(clauses, vectors, strict=True))
                ],
            )
    log.info("%s : %d clauses indexées", source["id"], len(clauses))
    return True
