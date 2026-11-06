"""make stats: counts per contract. make inspect ID=...: the clause tree of one contract."""

import json
import sys
from collections import Counter

from app.config import get_settings
from app.db.session import connect

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

with connect() as conn:
    if len(sys.argv) > 1:
        for c in conn.execute(
            "SELECT id, numero, chemin, type, page_debut, length(texte) n FROM clauses WHERE contract_id = %s ORDER BY ordre",
            (sys.argv[1],),
        ):
            print(f"p.{c['page_debut']:>3} {c['type']:<13} {c['numero'] or '':<10} {c['chemin'][-90:]} ({c['n']} car.)")
        sys.exit()
    tables = ["clauses", "garanties", "exclusions", "definitions", "conditions", "plafonds"]
    counts = {
        t: {r["contract_id"]: r["count"] for r in conn.execute(f"SELECT contract_id, count(*) FROM {t} GROUP BY 1")}
        for t in tables
    }

path = get_settings().data_dir / "extraction_rejets.jsonl"
rejets = Counter(json.loads(line)["contract_id"] for line in path.open(encoding="utf-8")) if path.exists() else Counter()
print(f"{'contrat':<30}" + "".join(f"{t:>12}" for t in tables) + f"{'rejets':>10}")
for cid in sorted(counts["clauses"]):
    kept = sum(counts[t].get(cid, 0) for t in tables[1:])
    taux = f"{100 * rejets[cid] / (kept + rejets[cid]):.0f} %" if kept + rejets[cid] else "-"
    print(f"{cid:<30}" + "".join(f"{counts[t].get(cid, 0):>12}" for t in tables) + f"{taux:>10}")
