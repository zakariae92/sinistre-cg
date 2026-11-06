"""FastAPI app: JSON API (/api/*) and server-rendered pages (Jinja2 + htmx)."""

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import truststore
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.analysis import pipeline
from app.analysis.schemas import Analyse, Faits
from app.config import ROOT, get_settings
from app.db.session import connect, init_schema
from app.ingestion.extract import TABLES
from app.ingestion.fetch import load_sources, pdf_path

truststore.inject_into_ssl()
log = logging.getLogger(__name__)
WEB = Path(__file__).parent / "web"
templates = Jinja2Templates(WEB / "templates")
templates.env.filters["tojson_pretty"] = lambda v: json.dumps(v, ensure_ascii=False, indent=2, default=str)

EXEMPLES = [
    "Mon vélo a été volé dans le local à vélos commun de mon immeuble.",
    "Mon vélo a été volé dans le local à vélos commun de mon immeuble. Le local n'était pas fermé à clé.",
    "Pendant mes vacances, une bougie restée allumée sur la terrasse a brûlé ma table de jardin.",
    "Des cambrioleurs ont forcé la porte d'entrée de mon appartement et ont volé mon ordinateur portable.",
    "Une fuite de ma machine à laver a abîmé le parquet et le plafond du voisin du dessous.",
    "Mon fils de 10 ans a cassé la vitre du voisin avec son ballon.",
]


@asynccontextmanager
async def lifespan(_: FastAPI):  # type: ignore[no-untyped-def]
    init_schema()
    task = asyncio.create_task(precompute()) if get_settings().precompute else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="Sinistre & Conditions Générales", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=WEB / "static"), name="static")


# --- rate limit: per IP per hour + global daily cap, on analyses that actually call the LLM ------
_par_ip: dict[str, deque[float]] = defaultdict(deque)
_jour: deque[float] = deque()


def check_quota(request: Request) -> None:
    # shortcut: in-process counters, reset on restart and wrong with several workers; use Redis then.
    s, now = get_settings(), time.time()
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0]
    for q, window in ((_par_ip[ip], 3600), (_jour, 86400)):
        while q and q[0] < now - window:
            q.popleft()
    if len(_par_ip[ip]) >= s.max_analyses_par_ip_heure:
        raise HTTPException(429, "Limite atteinte : 10 analyses par heure. Les exemples restent disponibles.")
    if len(_jour) >= s.max_analyses_par_jour:
        raise HTTPException(429, "Plafond quotidien de la démo atteint. Les exemples restent disponibles.")
    _par_ip[ip].append(now)
    _jour.append(now)


# --- data helpers ----------------------------------------------------------------------------
def contracts() -> list[dict[str, Any]]:
    with connect() as conn:
        return conn.execute("SELECT * FROM contracts WHERE extracted_sha256 IS NOT NULL ORDER BY pays DESC, assureur").fetchall()


def contract_ids() -> list[str]:
    return [c["id"] for c in contracts()]


async def precompute() -> None:
    """Warm the cache with the home-page examples on every contract: the demo is instant and free."""
    for recit in EXEMPLES:
        for cid in contract_ids():
            try:
                await pipeline.analyse(cid, recit)
            except Exception:
                log.exception("pré-calcul %s", cid)


async def run_analysis(request: Request, contract_id: str, recit: str, faits: Faits | None) -> Analyse:
    if contract_id not in contract_ids():
        raise HTTPException(404, "Contrat inconnu")
    if not recit.strip() or len(recit) > 2000:
        raise HTTPException(422, "Décrivez le sinistre (2 000 caractères maximum).")
    f = faits or await pipeline.qualify(recit)
    if not pipeline.is_cached(contract_id, f):
        check_quota(request)
    return await pipeline.analyse(contract_id, recit, f)


# --- JSON API -------------------------------------------------------------------------------
class AnalyseIn(BaseModel):
    contract_id: str
    recit: str
    faits: Faits | None = None


class ComparerIn(BaseModel):
    recit: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyse")
async def api_analyse(body: AnalyseIn, request: Request) -> Analyse:
    return await run_analysis(request, body.contract_id, body.recit, body.faits)


@app.post("/api/comparer")
async def api_comparer(body: ComparerIn, request: Request) -> dict[str, Any]:
    faits, results = await comparer(request, body.recit)
    return {"faits": faits, "resultats": results}


async def comparer(request: Request, recit: str) -> tuple[Faits, list[Analyse | str]]:
    if not recit.strip() or len(recit) > 2000:
        raise HTTPException(422, "Décrivez le sinistre (2 000 caractères maximum).")
    ids = contract_ids()
    faits = await pipeline.qualify(recit)
    if not all(pipeline.is_cached(c, faits) for c in ids):
        check_quota(request)
    return await pipeline.compare(recit, ids)


# --- pages ----------------------------------------------------------------------------------
def page(request: Request, name: str, **ctx: Any) -> HTMLResponse:
    return templates.TemplateResponse(request, name, {"contrats": contracts(), "exemples": EXEMPLES, **ctx})


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return page(request, "index.html")


@app.post("/analyser", response_class=HTMLResponse)
async def analyser(
    request: Request,
    contract_id: str = Form(),
    recit: str = Form(),
    faits: str = Form(""),
    question: str = Form(""),
    fait: str = Form(""),
    reponse: str = Form(""),
) -> HTMLResponse:
    try:
        if contract_id == "tous":
            f, results = await comparer(request, recit)
            return page(
                request,
                "_comparaison.html",
                faits=f,
                resultats=results,
                recit=recit,
                noms={c["id"]: c for c in contracts()},
            )
        current = Faits.model_validate_json(faits) if faits else None
        if current and question:
            current = pipeline.apply_answer(current, fait, question, reponse)
        a = await run_analysis(request, contract_id, recit, current)
    except HTTPException as e:
        return page(request, "_erreur.html", message=e.detail)
    except Exception:
        log.exception("analyse")
        return page(request, "_erreur.html", message="L'analyse a échoué (fournisseur LLM indisponible ?). Réessayez.")
    contrat = next(c for c in contracts() if c["id"] == contract_id)
    return page(request, "_resultat.html", a=a, recit=recit, contrat=contrat)


@app.get("/comparer", response_class=HTMLResponse)
def comparer_page(request: Request) -> HTMLResponse:
    return page(request, "index.html", selection="tous")


@app.get("/contrats", response_class=HTMLResponse)
def contrats_page(request: Request) -> HTMLResponse:
    with connect() as conn:
        rows = {t: conn.execute(f"SELECT * FROM {t} ORDER BY contract_id, id").fetchall() for t in TABLES}
        clauses = {
            r["id"]: r
            for r in conn.execute(
                "SELECT id, numero, titre, page_debut, bboxes FROM clauses WHERE id = ANY(%s)",
                ([i for t in rows.values() for r in t for i in r["clause_ids"]],),
            ).fetchall()
        }
    matrice: dict[str, dict[str, str]] = defaultdict(dict)
    for g in rows["garanties"]:
        prev = matrice[g["categorie"]].get(g["contract_id"])
        matrice[g["categorie"]][g["contract_id"]] = "✓" if not g["optionnelle"] or prev == "✓" else "option"
    return page(request, "contrats.html", rows=rows, clauses=clauses, matrice=dict(sorted(matrice.items())))


@app.get("/evaluation", response_class=HTMLResponse)
def evaluation_page(request: Request) -> HTMLResponse:
    path = ROOT / "eval" / "results.json"
    results = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    return page(request, "evaluation.html", ev=results)


@app.get("/a-propos", response_class=HTMLResponse)
def apropos(request: Request) -> HTMLResponse:
    return page(request, "a_propos.html")


@app.get("/pdf/{contract_id}")
def pdf(contract_id: str) -> FileResponse:
    source = next((s for s in load_sources() if s["id"] == contract_id), None)
    if not source or not pdf_path(source).exists():
        raise HTTPException(404)
    return FileResponse(pdf_path(source), media_type="application/pdf")
