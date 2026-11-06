"""Claim analysis: qualify -> retrieve -> reason -> verify (one retry), cached in Postgres."""

import asyncio
import hashlib
import json
import time
from typing import Any

from psycopg.types.json import Jsonb

from app.analysis import verify
from app.analysis.retrieve import retrieve
from app.analysis.schemas import Analyse, ClauseRef, Faits, Resultat
from app.db.session import connect
from app.llm.client import PROMPT_VERSION, get_llm, prompt


def _key(*parts: Any) -> str:
    return hashlib.sha256(json.dumps([PROMPT_VERSION, *parts], sort_keys=True, default=str).encode()).hexdigest()


def cache_get(key: str) -> Any | None:
    with connect() as conn:
        row = conn.execute("SELECT value FROM cache WHERE key = %s", (key,)).fetchone()
    return row["value"] if row else None


def cache_put(key: str, value: Any) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO cache (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            (key, Jsonb(value)),
        )


def is_cached(contract_id: str, faits: Faits) -> bool:
    return cache_get(_key("analyse", contract_id, faits.model_dump(mode="json"))) is not None


async def qualify(recit: str) -> Faits:
    key = _key("faits", recit.strip())
    if (hit := cache_get(key)) is not None:
        return Faits.model_validate(hit)
    faits = await get_llm().structured(prompt("qualify"), recit, Faits)
    cache_put(key, faits.model_dump(mode="json"))
    return faits


def _context(clauses: list[dict[str, Any]]) -> str:
    return "\n\n".join(
        f'<clause id="{c["id"]}" numero="{c["numero"] or ""}" chemin="{c["chemin"]}" page="{c["page_debut"]}">\n'
        f"{c['texte']}\n</clause>"
        for c in clauses
    )


async def analyse(contract_id: str, recit: str, faits: Faits | None = None) -> Analyse:
    faits = faits or await qualify(recit)
    key = _key("analyse", contract_id, faits.model_dump(mode="json"))
    if (hit := cache_get(key)) is not None:
        return Analyse.model_validate(hit)

    start = time.perf_counter()
    clauses = await asyncio.to_thread(retrieve, contract_id, faits, recit)
    with connect() as conn:
        c = conn.execute("SELECT assureur, produit, pays, langue FROM contracts WHERE id = %s", (contract_id,)).fetchone()
    if not c:
        raise ValueError(f"contrat inconnu : {contract_id}")
    llm = get_llm()
    user = (
        f"Contrat : {c['assureur']} – {c['produit']} ({c['pays']}, rédigé en {c['langue']})\n\n"
        f"Récit de l'assuré :\n{recit}\n\nFaits structurés :\n{faits.model_dump_json(indent=1)}\n\n"
        f"Clauses fournies :\n{_context(clauses)}"
    )
    system = prompt("reason")
    resultat = await llm.structured(system, user, Resultat)
    texts = {cl["id"]: cl["texte"] for cl in clauses}
    errs = verify.errors(resultat, texts)
    if errs:  # one retry, telling the model exactly what failed
        fix = "\n\nTa réponse précédente contenait des citations invalides :\n- " + "\n- ".join(errs)
        resultat = await llm.structured(system, user + fix + "\nCorrige-les (copie exacte) ou retire l'étape.", Resultat)
    resultat, verification = verify.enforce(resultat, texts, retried=bool(errs))

    by_id = {cl["id"]: cl for cl in clauses}
    cited = {ct.clause_id for e in resultat.etapes for ct in e.citations}
    out = Analyse(
        contract_id=contract_id,
        faits=faits,
        resultat=resultat,
        verification=verification,
        clauses={
            i: ClauseRef(
                id=i,
                numero=by_id[i]["numero"],
                titre=by_id[i]["titre"],
                page_debut=by_id[i]["page_debut"],
                bboxes=by_id[i]["bboxes"],
            )
            for i in cited
        },
        modele=llm.model,
        latence_ms=int((time.perf_counter() - start) * 1000),
    )
    cache_put(key, out.model_dump(mode="json"))
    return out


def apply_answer(faits: Faits, fait: str, question: str, reponse: str) -> Faits:
    """Clarification loop: a yes/no answer sets the boolean fact; every answer is kept as a précision."""
    update: dict[str, Any] = {"precisions": [*faits.precisions, f"{question} → {reponse}"]}
    if fait in Faits.model_fields and Faits.model_fields[fait].annotation == (bool | None):
        update[fait] = {"oui": True, "non": False}.get(reponse.lower())
    return faits.model_copy(update=update)


async def compare(recit: str, contract_ids: list[str]) -> tuple[Faits, list[Analyse | str]]:
    faits = await qualify(recit)
    sem = asyncio.Semaphore(3)

    async def one(cid: str) -> Analyse | str:
        async with sem:
            try:
                return await analyse(cid, recit, faits)
            except Exception as e:  # one failing contract must not sink the whole table
                return f"{cid} : {e}"

    return faits, list(await asyncio.gather(*(one(c) for c in contract_ids)))
