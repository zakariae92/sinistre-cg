"""Download the public general conditions and reject what is not a full contract (e.g. an IPID)."""

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pymupdf
import yaml

from app.config import ROOT, get_settings

log = logging.getLogger(__name__)
SOURCES = ROOT / "corpus" / "sources.yaml"
MIN_PAGES = 15


def load_sources() -> list[dict[str, Any]]:
    return yaml.safe_load(SOURCES.read_text(encoding="utf-8"))


def pdf_path(source: dict[str, Any]) -> Path:
    raw = get_settings().data_dir / "raw"
    url: str = source["url"]
    if url.startswith("manual://"):
        return raw / "manual" / url.removeprefix("manual://")
    return raw / f"{source['id']}.pdf"


@dataclass
class Check:
    id: str
    statut: str  # ok | rejete | erreur
    pages: int = 0
    sha256: str = ""
    raison: str = ""


def check_pdf(path: Path) -> Check:
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as e:
        return Check(path.stem, "rejete", 0, sha, f"PDF illisible : {e}")
    text = " ".join(page.get_text() for page in doc).lower()  # type: ignore[attr-defined]
    pages = doc.page_count
    if pages < MIN_PAGES:
        return Check(path.stem, "rejete", pages, sha, f"{pages} pages : probablement une fiche IPID")
    # Stems: "exclus", "définit", English "definition"; a glossary may be called "lexique".
    if "exclu" not in text or not ("défini" in text or "definition" in text or "lexique" in text):
        return Check(path.stem, "rejete", pages, sha, "pas de section exclusions/définitions")
    return Check(path.stem, "ok", pages, sha)


def fetch(source: dict[str, Any], client: httpx.Client) -> Check:
    path = pdf_path(source)
    if not path.exists():
        if source["url"].startswith("manual://"):
            return Check(source["id"], "erreur", raison=f"déposer le PDF dans {path}")
        try:
            r = client.get(source["url"])
            r.raise_for_status()
        except httpx.HTTPError as e:
            return Check(source["id"], "erreur", raison=f"téléchargement : {str(e).splitlines()[0]}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.content)
    result = check_pdf(path)
    result.id = source["id"]
    if result.statut != "ok":
        log.warning("%s rejeté : %s", source["id"], result.raison)
    return result


def fetch_all() -> list[Check]:
    headers = {"User-Agent": "Mozilla/5.0 (sinistre-cg demo; public documents)"}
    with httpx.Client(follow_redirects=True, timeout=60, headers=headers) as client:
        return [fetch(s, client) for s in load_sources()]
