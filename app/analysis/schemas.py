from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Verdict = Literal["COUVERT", "NON_COUVERT", "AMBIGU", "INFORMATION_MANQUANTE"]


class Faits(BaseModel):
    """Facts extracted from the claim narrative. Unknown = null, never a guess."""

    evenement: Literal[
        "vol",
        "incendie",
        "degats_des_eaux",
        "bris_de_glace",
        "tempete_grele",
        "vandalisme",
        "degats_electriques",
        "responsabilite_civile",
        "autre",
    ]
    biens: list[str]
    lieu: Literal[
        "interieur_logement",
        "dependance_privative",
        "partie_commune",
        "exterieur_jardin_terrasse",
        "hors_domicile",
        "inconnu",
    ]
    effraction: bool | None
    local_ferme_a_cle: bool | None
    logement_inoccupe: bool | None
    duree_inoccupation_jours: int | None
    cause: str | None
    tiers_implique: bool | None
    date_sinistre: date | None
    resume: str
    precisions: list[str] = Field(default_factory=list)  # answers given to the follow-up questions


class Citation(BaseModel):
    clause_id: str
    extrait: str


class Etape(BaseModel):
    type: Literal["garantie", "condition", "exclusion", "definition", "plafond", "conclusion"]
    affirmation: str
    citations: list[Citation]


class Question(BaseModel):
    texte: str
    fait_concerne: str


class Resultat(BaseModel):
    verdict: Verdict
    resume: str
    etapes: list[Etape]
    ambiguites: list[str]
    questions: list[Question]
    confiance: Literal["haute", "moyenne", "faible"]


class Verification(BaseModel):
    citations_verifiees: int = 0
    citations_rejetees: int = 0
    etapes_retirees: int = 0
    nouvel_essai: bool = False


class ClauseRef(BaseModel):
    id: str
    numero: str | None
    titre: str
    page_debut: int
    bboxes: list[list[float]]


class Analyse(BaseModel):
    contract_id: str
    faits: Faits
    resultat: Resultat
    verification: Verification
    clauses: dict[str, ClauseRef]  # every clause cited, for the PDF viewer
    modele: str
    latence_ms: int
