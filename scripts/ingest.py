"""make ingest [ID=...]: parse + index + structured extraction. Idempotent (sha256)."""

import asyncio
import logging
import sys

import truststore

from app.db.session import init_schema
from app.ingestion.extract import extract_contract
from app.ingestion.fetch import load_sources, pdf_path
from app.ingestion.index import index_contract

truststore.inject_into_ssl()
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

only = sys.argv[1] if len(sys.argv) > 1 else None
init_schema()
for source in load_sources():
    if (only and source["id"] != only) or not pdf_path(source).exists():
        continue
    index_contract(source)
    print(source["id"], asyncio.run(extract_contract(source["id"])) or "déjà à jour")
