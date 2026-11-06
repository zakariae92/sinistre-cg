"""« Pas de citation, pas d'affirmation » : every quote must exist in a clause that was in the context."""

from app.analysis.schemas import Resultat, Verification
from app.ingestion.validate import citation_ok


def errors(resultat: Resultat, context: dict[str, str]) -> list[str]:
    out = []
    for i, etape in enumerate(resultat.etapes):
        if not etape.citations:
            out.append(f"étape {i + 1} ({etape.type}) : aucune citation")
        for c in etape.citations:
            if c.clause_id not in context:
                out.append(f"étape {i + 1} : la clause {c.clause_id} ne fait pas partie des clauses fournies")
            elif not citation_ok(c.extrait, context[c.clause_id]):
                out.append(f"étape {i + 1} : l'extrait « {c.extrait[:80]} » n'est pas dans la clause {c.clause_id}")
    return out


def enforce(resultat: Resultat, context: dict[str, str], retried: bool) -> tuple[Resultat, Verification]:
    """Drop unverifiable citations and steps, then apply the verdict rules."""
    v = Verification(nouvel_essai=retried)
    kept = []
    dropped_key_step = False
    for etape in resultat.etapes:
        good = [c for c in etape.citations if c.clause_id in context and citation_ok(c.extrait, context[c.clause_id])]
        v.citations_verifiees += len(good)
        v.citations_rejetees += len(etape.citations) - len(good)
        if good:
            kept.append(etape.model_copy(update={"citations": good}))
        else:
            v.etapes_retirees += 1
            dropped_key_step |= etape.type in ("garantie", "exclusion")
    r = resultat.model_copy(update={"etapes": kept})
    types = {e.type for e in kept}
    if dropped_key_step and r.verdict in ("COUVERT", "NON_COUVERT"):
        r.verdict = "AMBIGU"
        r.ambiguites.append("Citation non vérifiable : une étape clé du raisonnement a été retirée.")
    if r.verdict == "COUVERT" and not {"garantie", "exclusion"} <= types:
        r.verdict = "AMBIGU"
        r.ambiguites.append("Couverture non démontrée : garantie ou vérification des exclusions sans citation vérifiée.")
    if r.verdict == "INFORMATION_MANQUANTE" and not r.questions:
        r.verdict = "AMBIGU"
    return r, v
