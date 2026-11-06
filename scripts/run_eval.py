"""make eval [CONTRAT=...]: run eval/cases.yaml -> eval/results.json + eval/REPORT.md."""

import asyncio
import json
import statistics
import sys
from datetime import date

import truststore
import yaml

from app.analysis.pipeline import analyse
from app.config import ROOT, get_settings

truststore.inject_into_ssl()
VERDICTS = ["COUVERT", "NON_COUVERT", "AMBIGU", "INFORMATION_MANQUANTE"]
contract_id = sys.argv[1] if len(sys.argv) > 1 else "axa-lu-optihome"
cases = yaml.safe_load((ROOT / "eval" / "cases.yaml").read_text(encoding="utf-8"))


async def run_case(case: dict) -> dict:
    exp = case["attendu"]
    accepted = exp["verdict"].split("|")
    row = {
        "id": case["id"],
        "recit": case["recit"],
        "contract_id": contract_id,
        "tags": case["tags"],
        "attendu": accepted[0],
        "acceptes": accepted,
        "propose": exp.get("propose", True),
        "note": exp.get("note", ""),
    }
    try:
        a = await analyse(contract_id, case["recit"])
    except Exception as e:
        return row | {"obtenu": None, "erreur": str(e)[:200], "citations_verifiees": 0, "citations_rejetees": 0}
    got = a.resultat.verdict
    cited = {c.clause_id for e in a.resultat.etapes for c in e.citations}
    expected_clauses = set(exp.get("clauses") or [])
    row |= {
        "obtenu": got,
        "ok": got in accepted,
        "latence_ms": a.latence_ms,
        "citations_verifiees": a.verification.citations_verifiees,
        "citations_rejetees": a.verification.citations_rejetees,
        "rappel": len(cited & expected_clauses) / len(expected_clauses) if expected_clauses else None,
    }
    if got in accepted:
        row["attendu"] = got  # matched one of the accepted verdicts
    else:
        row["note"] = f"obtenu {got}, attendu {exp['verdict']}. {row['note']}"
    return row


async def main() -> None:
    sem = asyncio.Semaphore(2)

    async def guarded(c: dict) -> dict:
        async with sem:
            return await run_case(c)

    rows = await asyncio.gather(*(guarded(c) for c in cases))
    done = [r for r in rows if r["obtenu"]]
    validated = [r for r in done if not r["propose"]]
    ambigus = [r for r in done if "ambigu" in r["tags"]]
    verif = sum(r["citations_verifiees"] for r in rows)
    total = verif + sum(r["citations_rejetees"] for r in rows)
    lat = sorted(r["latence_ms"] for r in done if r["latence_ms"] > 0)
    rappels = [r["rappel"] for r in done if r["rappel"] is not None]

    def pct(xs: list, pred) -> float | None:  # type: ignore[no-untyped-def]
        return round(100 * sum(map(pred, xs)) / len(xs)) if xs else None

    confusion = {a: {b: 0 for b in VERDICTS} for a in VERDICTS}
    for r in done:
        confusion[r["attendu"]][r["obtenu"]] += 1
    results = {
        "date": str(date.today()),
        "modele": get_settings().llm_model,
        "nb_cas": len(rows),
        "verdicts": VERDICTS,
        "metriques": {
            "exactitude": pct(done, lambda r: r["ok"]),
            "exactitude_validee": pct(validated, lambda r: r["ok"]),
            "fidelite": round(100 * verif / total) if total else None,
            "rappel_clauses": round(100 * statistics.mean(rappels)) if rappels else None,
            "detection_ambiguites": pct(ambigus, lambda r: r["obtenu"] in ("AMBIGU", "INFORMATION_MANQUANTE")),
            "latence": f"{lat[len(lat) // 2] / 1000:.0f} s / {lat[int(len(lat) * 0.95) - 1] / 1000:.0f} s" if lat else None,
        },
        "confusion": confusion,
        "cas": rows,
    }
    (ROOT / "eval" / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    m = results["metriques"]
    lines = [
        f"# Rapport d'évaluation ({contract_id}, {results['date']}, {results['modele']})",
        "",
        *(f"- **{k}** : {v}" for k, v in m.items()),
        "",
        "| cas | attendu | obtenu | ok | citations ✓/✗ | note |",
        "|---|---|---|---|---|---|",
    ]
    lines += [
        f"| {r['id']} | {'/'.join(r['acceptes'])}{' (proposé)' if r['propose'] else ''} | {r['obtenu'] or r.get('erreur')} | "
        f"{'✅' if r.get('ok') else '❌'} | {r['citations_verifiees']}/{r['citations_rejetees']} | {r['note']} |"
        for r in rows
    ]
    (ROOT / "eval" / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:9]))


asyncio.run(main())
