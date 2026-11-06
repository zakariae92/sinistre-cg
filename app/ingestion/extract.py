"""Structured extraction: clauses -> garanties / exclusions / définitions / conditions / plafonds.

Every extracted item must point to clauses of the batch and carry a quote found in them;
anything else is rejected and logged to data/extraction_rejets.jsonl.
"""

import asyncio
import json
import logging
import unicodedata
from typing import Any, Literal

from pydantic import BaseModel

from app.config import get_settings
from app.db.session import connect
from app.ingestion.validate import citation_ok
from app.llm.client import get_llm, prompt

log = logging.getLogger(__name__)
BATCH_CHARS = 20_000

Categorie = Literal[
    "incendie",
    "degats_des_eaux",
    "vol",
    "vandalisme",
    "bris_de_glace",
    "tempete_grele",
    "catastrophes_naturelles",
    "degats_electriques",
    "responsabilite_civile_vie_privee",
    "responsabilite_locative",
    "mobilier_exterieur_jardin",
    "objets_de_valeur",
    "assistance",
    "protection_juridique",
    "autre",
]
TypeClause = Literal["garantie", "exclusion", "definition", "condition", "plafond", "administratif", "autre"]


class Source(BaseModel):
    clause_ids: list[str]
    citation: str  # short verbatim quote


class Garantie(Source):
    nom: str
    categorie: Categorie
    description: str
    optionnelle: bool


class Exclusion(Source):
    categorie: Categorie | None  # None = exclusion générale (toutes garanties)
    description: str


class Definition(Source):
    terme: str
    definition: str


class Condition(Source):
    categorie: Categorie
    description: str


class Plafond(Source):
    categorie: Categorie
    libelle: str
    montant: str | None
    franchise: str | None


class TypeDeClause(BaseModel):
    clause_id: str
    type: TypeClause


class Extraction(BaseModel):
    types: list[TypeDeClause]
    garanties: list[Garantie]
    exclusions: list[Exclusion]
    definitions: list[Definition]
    conditions: list[Condition]
    plafonds: list[Plafond]


def terme_normalise(terme: str) -> str:
    s = unicodedata.normalize("NFKD", terme.lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip(" .:")


def batches(clauses: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    out: list[list[dict[str, Any]]] = [[]]
    size = 0
    for c in clauses:
        if size > BATCH_CHARS:
            out.append([])
            size = 0
        out[-1].append(c)
        size += len(c["texte"]) + len(c["chemin"])
    return out


def render(clauses: list[dict[str, Any]]) -> str:
    return "\n\n".join(f'<clause id="{c["id"]}" chemin="{c["chemin"]}">\n{c["texte"]}\n</clause>' for c in clauses)


TABLES = {
    "garanties": Garantie,
    "exclusions": Exclusion,
    "definitions": Definition,
    "conditions": Condition,
    "plafonds": Plafond,
}


def validate(result: Extraction, by_id: dict[str, str]) -> tuple[dict[str, list[Source]], list[dict[str, Any]]]:
    kept: dict[str, list[Source]] = {k: [] for k in TABLES}
    rejects = []
    for table in TABLES:
        for item in getattr(result, table):
            ids = [i for i in item.clause_ids if i in by_id]
            texte = "\n".join(by_id[i] for i in ids)
            if ids and citation_ok(item.citation, texte):
                item.clause_ids = ids
                kept[table].append(item)
            else:
                reason = "clause inconnue" if not ids else "citation introuvable"
                rejects.append({"table": table, "raison": reason, **item.model_dump()})
    return kept, rejects


async def extract_contract(contract_id: str, force: bool = False) -> dict[str, int]:
    with connect() as conn:
        c = conn.execute("SELECT * FROM contracts WHERE id = %s", (contract_id,)).fetchone()
        if not c:
            raise ValueError(f"contrat inconnu : {contract_id}")
        if c["extracted_sha256"] == c["sha256"] and not force:
            return {}
        clauses = conn.execute(
            "SELECT id, chemin, texte FROM clauses WHERE contract_id = %s ORDER BY ordre", (contract_id,)
        ).fetchall()
    llm = get_llm(get_settings().extract_model, thinking="low")  # long outputs: thinking dominates latency
    system = prompt("extract")
    sem = asyncio.Semaphore(6)

    async def run(batch: list[dict[str, Any]]) -> Extraction:
        async with sem:
            header = f"Contrat : {c['assureur']} – {c['produit']} ({c['pays']}, langue {c['langue']})\n\n"
            return await llm.structured(system, header + render(batch), Extraction)

    parts = batches(clauses)
    results = await asyncio.gather(*(run(b) for b in parts))
    stats = {k: 0 for k in TABLES} | {"rejets": 0}
    rejets_path = get_settings().data_dir / "extraction_rejets.jsonl"
    with connect() as conn, rejets_path.open("a", encoding="utf-8") as rejets:
        for table in TABLES:
            conn.execute(f"DELETE FROM {table} WHERE contract_id = %s", (contract_id,))
        for batch, result in zip(parts, results, strict=True):
            by_id = {cl["id"]: cl["texte"] for cl in batch}
            for t in result.types:
                if t.clause_id in by_id:
                    conn.execute("UPDATE clauses SET type = %s WHERE id = %s", (t.type, t.clause_id))
            kept, rejects = validate(result, by_id)
            for r in rejects:
                rejets.write(json.dumps({"contract_id": contract_id, **r}, ensure_ascii=False) + "\n")
            stats["rejets"] += len(rejects)
            for table, items in kept.items():
                stats[table] += len(items)
                for item in items:
                    _insert(conn, table, contract_id, item)
        conn.execute("UPDATE contracts SET extracted_sha256 = sha256 WHERE id = %s", (contract_id,))
    log.info("%s : %s", contract_id, stats)
    return stats


def _insert(conn: Any, table: str, contract_id: str, item: Source) -> None:
    row = item.model_dump()
    if table == "definitions":
        row["terme_normalise"] = terme_normalise(row["terme"])
    cols = ["contract_id", *row]
    conn.execute(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})",
        [contract_id, *row.values()],
    )
