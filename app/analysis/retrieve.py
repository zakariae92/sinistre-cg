"""Targeted retrieval: structured base first (SQL), hybrid search (FTS + vectors) as a safety net."""

from typing import Any

from app.analysis.schemas import Faits
from app.db.session import connect
from app.ingestion.extract import terme_normalise
from app.ingestion.index import embed

CATEGORIES = {
    "vol": ["vol"],
    "vandalisme": ["vandalisme", "vol"],
    "incendie": ["incendie"],
    "degats_des_eaux": ["degats_des_eaux"],
    "bris_de_glace": ["bris_de_glace"],
    "tempete_grele": ["tempete_grele", "catastrophes_naturelles"],
    "degats_electriques": ["degats_electriques"],
    "responsabilite_civile": ["responsabilite_civile_vie_privee", "responsabilite_locative"],
    "autre": [],
}
TERMES_CLES = ["effraction", "local", "dependance", "inoccupation", "mobilier", "partie commune", "jardin"]
MAX_CLAUSES = 30


def categories(faits: Faits) -> list[str]:
    cats = list(CATEGORIES[faits.evenement])
    if faits.lieu == "exterieur_jardin_terrasse":
        cats.append("mobilier_exterieur_jardin")
    if any(b for b in faits.biens if "bijou" in b.lower() or "valeur" in b.lower()):
        cats.append("objets_de_valeur")
    return cats


def _ids(rows: list[dict[str, Any]]) -> list[str]:
    return [i for r in rows for i in r["clause_ids"]]


def hybrid(conn: Any, contract_id: str, query: str, k: int = 8) -> list[str]:
    """Reciprocal rank fusion of French full-text and BGE-M3 vector search."""
    fts = conn.execute(
        """SELECT id FROM clauses, websearch_to_tsquery('french', %s) q
           WHERE contract_id = %s AND tsv @@ q ORDER BY ts_rank(tsv, q) DESC LIMIT 20""",
        (" or ".join(w for w in query.split() if len(w) > 3), contract_id),
    ).fetchall()
    vec = conn.execute(
        "SELECT id FROM clauses WHERE contract_id = %s ORDER BY embedding <=> %s LIMIT 20",
        (contract_id, embed([query])[0]),
    ).fetchall()
    scores: dict[str, float] = {}
    for ranking in (fts, vec):
        for rank, row in enumerate(ranking):
            scores[row["id"]] = scores.get(row["id"], 0) + 1 / (60 + rank)
    return sorted(scores, key=lambda i: -scores[i])[:k]


def retrieve(contract_id: str, faits: Faits, recit: str) -> list[dict[str, Any]]:
    cats = categories(faits)
    with connect() as conn:
        q = "SELECT clause_ids FROM {t} WHERE contract_id = %s AND categorie = ANY(%s)"
        ordered = (
            _ids(conn.execute(q.format(t="garanties"), (contract_id, cats)).fetchall())
            + _ids(conn.execute(q.format(t="conditions"), (contract_id, cats)).fetchall())
            + _ids(conn.execute(q.format(t="exclusions"), (contract_id, cats)).fetchall())
            + _ids(conn.execute(q.format(t="plafonds"), (contract_id, cats)).fetchall())
            + _ids(
                conn.execute(
                    "SELECT clause_ids FROM exclusions WHERE contract_id = %s AND categorie IS NULL", (contract_id,)
                ).fetchall()
            )
        )
        ids = list(dict.fromkeys(ordered))[:20]
        texte = terme_normalise(" ".join([recit, *faits.biens, faits.cause or ""]))
        defs = conn.execute(
            "SELECT terme_normalise, clause_ids FROM definitions WHERE contract_id = %s", (contract_id,)
        ).fetchall()
        wanted = [d for d in defs if d["terme_normalise"] in texte or any(t in d["terme_normalise"] for t in TERMES_CLES)]
        ids += _ids(wanted)[:6]
        ids += hybrid(conn, contract_id, f"{faits.resume} {recit}")
        ids = list(dict.fromkeys(ids))[:MAX_CLAUSES]
        rows = conn.execute(
            "SELECT id, numero, titre, chemin, texte, page_debut, bboxes FROM clauses WHERE id = ANY(%s)", (ids,)
        ).fetchall()
    by_id = {r["id"]: r for r in rows}
    return [by_id[i] for i in ids if i in by_id]
