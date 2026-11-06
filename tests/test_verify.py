from app.analysis.pipeline import apply_answer
from app.analysis.schemas import Citation, Etape, Faits, Question, Resultat
from app.analysis.verify import enforce, errors
from app.ingestion.validate import citation_ok

CLAUSE = "Le vol n'est garanti que s'il est commis par effraction des locaux renfermant les biens assurés."
CTX = {"c:1": CLAUSE, "c:2": "Sont exclus les vols commis dans les parties communes de l'immeuble."}


def resultat(verdict: str, etapes: list[Etape]) -> Resultat:
    return Resultat(verdict=verdict, resume="r", etapes=etapes, ambiguites=[], questions=[], confiance="moyenne")  # type: ignore[arg-type]


def step(type_: str, cid: str, extrait: str) -> Etape:
    return Etape(type=type_, affirmation="a", citations=[Citation(clause_id=cid, extrait=extrait)])  # type: ignore[arg-type]


def test_citation_match_is_normalised_and_fuzzy() -> None:
    assert citation_ok("commis par effraction des locaux", CLAUSE)
    assert citation_ok("Le vol n’est garanti que s’il est commis par effraction", CLAUSE)  # typographic quotes
    assert citation_ok("le vol n'est garanti que s'il est commis par efraction des locaux", CLAUSE)  # typo
    assert not citation_ok("le vol est toujours garanti", CLAUSE)
    assert not citation_ok("vol", CLAUSE)  # too short to prove anything


def test_unknown_clause_and_fake_quote_are_errors() -> None:
    r = resultat(
        "COUVERT",
        [
            step("garantie", "c:9", "commis par effraction des locaux"),
            step("exclusion", "c:2", "inventé de toutes pièces ici"),
        ],
    )
    assert len(errors(r, CTX)) == 2


def test_dropping_a_key_step_downgrades_verdict() -> None:
    r = resultat(
        "NON_COUVERT",
        [
            step("garantie", "c:1", "commis par effraction des locaux"),
            step("exclusion", "c:2", "citation qui n'existe pas dans la clause"),
        ],
    )
    out, v = enforce(r, CTX, retried=True)
    assert out.verdict == "AMBIGU"
    assert v.citations_verifiees == 1 and v.citations_rejetees == 1 and v.etapes_retirees == 1


def test_covered_requires_guarantee_and_exclusion_check() -> None:
    r = resultat("COUVERT", [step("garantie", "c:1", "commis par effraction des locaux")])
    assert enforce(r, CTX, retried=False)[0].verdict == "AMBIGU"
    r = resultat(
        "COUVERT",
        [
            step("garantie", "c:1", "commis par effraction des locaux"),
            step("exclusion", "c:2", "vols commis dans les parties communes"),
        ],
    )
    assert enforce(r, CTX, retried=False)[0].verdict == "COUVERT"


def test_missing_info_without_question_is_ambiguous() -> None:
    r = resultat("INFORMATION_MANQUANTE", [step("garantie", "c:1", "commis par effraction des locaux")])
    assert enforce(r, CTX, retried=False)[0].verdict == "AMBIGU"
    r.questions = [Question(texte="Le local était-il fermé ?", fait_concerne="local_ferme_a_cle")]
    assert enforce(r, CTX, retried=False)[0].verdict == "INFORMATION_MANQUANTE"


def test_answer_sets_boolean_fact() -> None:
    f = Faits(
        evenement="vol",
        biens=["vélo"],
        lieu="partie_commune",
        effraction=None,
        local_ferme_a_cle=None,
        logement_inoccupe=None,
        duree_inoccupation_jours=None,
        cause=None,
        tiers_implique=None,
        date_sinistre=None,
        resume="vol de vélo",
    )
    f2 = apply_answer(f, "local_ferme_a_cle", "Le local était-il fermé à clé ?", "non")
    assert f2.local_ferme_a_cle is False and len(f2.precisions) == 1
    assert apply_answer(f, "local_ferme_a_cle", "q", "je ne sais pas").local_ferme_a_cle is None
    assert apply_answer(f, "cause", "q", "oui").cause is None  # not a yes/no fact
