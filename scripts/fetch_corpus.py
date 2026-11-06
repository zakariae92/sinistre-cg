"""make fetch: download every source and write data/corpus_report.md."""

import logging

import truststore

from app.config import get_settings
from app.ingestion.fetch import fetch_all, load_sources

truststore.inject_into_ssl()  # corporate/antivirus TLS interception: trust the OS store
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

checks = fetch_all()
urls = {s["id"]: s["url"] for s in load_sources()}
lines = ["| id | statut | pages | sha256 | remarque |", "|---|---|---|---|---|"]
for c in checks:
    lines.append(f"| [{c.id}]({urls[c.id]}) | {c.statut} | {c.pages} | {c.sha256[:12]} | {c.raison} |")
report = get_settings().data_dir / "corpus_report.md"
report.write_text("# Rapport corpus\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
