# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Report formats (canevas) of donors and organisations (module M12).

A format is an ordered list of sections with the labels a donor uses. It follows
the structure of the donor's public reporting practice without reproducing any
official document: the user loads the exact Word template the donor hands over,
and the content generated here goes into it.

Section kinds filled from the project:

    tracking          indicators of the period: baseline, values, target, rate, status
    results           progress by result: indicators, gap explanations, activities
    gaps              explanations of the gaps
    activities        activities of the period, with their state
    next_activities   activities planned in the next period
    budget            budget execution by line
    beneficiaries     people reached (count indicators)
    feedback          feedback and complaints, counts only
    recommendations   follow-up of the recommendations
    risks             risks and assumptions in force
    lessons           lessons learned in the period
    surveys           survey estimates placed in the periods of the report
    evaluations       evaluations and their steps
    logframe          logframe matrix
    calendar          data collection calendar
    pirs              indicator reference sheets, one per indicator

and "text" sections the user writes in the application, kept from one
generation to the next.
"""

from __future__ import annotations

from typing import Any

KINDS = (
    "text",
    "tracking",
    "results",
    "gaps",
    "activities",
    "next_activities",
    "budget",
    "beneficiaries",
    "feedback",
    "recommendations",
    "risks",
    "lessons",
    "surveys",
    "evaluations",
    "logframe",
    "calendar",
    "pirs",
)


def S(kind: str, fr: str, en: str, key: str | None = None, hint_fr: str = "", hint_en: str = "") -> dict[str, Any]:
    return {"key": key or kind, "kind": kind, "fr": fr, "en": en, "hint_fr": hint_fr, "hint_en": hint_en}


def T(key: str, fr: str, en: str, hint_fr: str = "", hint_en: str = "") -> dict[str, Any]:
    return S("text", fr, en, key, hint_fr, hint_en)


SUMMARY = T(
    "summary",
    "Résumé",
    "Summary",
    "Les faits marquants de la période en quelques paragraphes : ce qui a avancé, ce qui a pris du retard, pourquoi.",
    "The highlights of the period in a few paragraphs: what moved forward, what fell behind, and why.",
)
CONTEXT = T(
    "context",
    "Contexte",
    "Context",
    "Évolutions du contexte qui ont pesé sur la mise en œuvre (sécurité, saison, prix, politique).",
    "Changes in the context that weighed on implementation (security, season, prices, policy).",
)
DIFFICULTIES = T(
    "difficulties",
    "Difficultés rencontrées et mesures prises",
    "Challenges and measures taken",
    "Chaque difficulté, son effet sur les résultats et ce qui a été fait.",
    "Each challenge, its effect on results and what was done about it.",
)
NEXT_STEPS = T(
    "next_steps",
    "Perspectives pour la période suivante",
    "Plans for the next period",
    "Priorités et activités prévues, ajustements décidés.",
    "Priorities and planned activities, adjustments decided.",
)
PARTNERSHIPS = T("partnerships", "Partenariats et coordination", "Partnerships and coordination")
CROSS = T(
    "cross_cutting",
    "Thèmes transversaux : genre, inclusion, environnement",
    "Cross-cutting themes: gender, inclusion, environment",
)
VISIBILITY = T("visibility", "Communication et visibilité", "Communication and visibility")
FINANCE_TEXT = T(
    "finance_comment",
    "Commentaire sur l'exécution financière",
    "Comment on financial execution",
    "Écarts entre prévu et dépensé, et leur raison.",
    "Gaps between planned and spent, and their reason.",
)
ANNEX_PIRS = S("pirs", "Annexe : fiches des indicateurs", "Annex: indicator reference sheets")
ANNEX_LOGFRAME = S("logframe", "Annexe : cadre logique", "Annex: logical framework")


def _f(fid: str, donor: str, fr: str, en: str, sections: list[dict[str, Any]]) -> dict[str, Any]:
    return {"id": fid, "donor": donor, "fr": fr, "en": en, "sections": sections, "builtin": True}


FORMATS: list[dict[str, Any]] = [
    _f(
        "generic",
        "",
        "Rapport d'avancement d'ONG",
        "NGO progress report",
        [
            SUMMARY,
            CONTEXT,
            S("tracking", "Tableau de suivi des indicateurs", "Indicator tracking table"),
            S("results", "Avancement par résultat", "Progress by result"),
            S("activities", "Activités de la période", "Activities of the period"),
            S("budget", "Exécution du budget", "Budget execution"),
            S("feedback", "Retours et plaintes", "Feedback and complaints"),
            S("risks", "Risques et hypothèses", "Risks and assumptions"),
            DIFFICULTIES,
            S("lessons", "Leçons apprises", "Lessons learned"),
            NEXT_STEPS,
            S("next_activities", "Activités prévues", "Planned activities"),
        ],
    ),
    _f(
        "eu",
        "Union européenne",
        "Union européenne : rapport narratif intermédiaire",
        "European Union: interim narrative report",
        [
            T("summary", "Résumé de l'action", "Summary of the action"),
            S(
                "results",
                "Évaluation de la mise en œuvre des activités et des résultats",
                "Assessment of implementation of activities and results",
            ),
            S("tracking", "Cadre logique mis à jour : indicateurs", "Updated logframe: indicators"),
            S("activities", "Activités réalisées", "Activities carried out"),
            T("beneficiaries_text", "Bénéficiaires et entités affiliées", "Beneficiaries and affiliated entities"),
            PARTNERSHIPS,
            S("risks", "Hypothèses et risques", "Assumptions and risks"),
            VISIBILITY,
            S("lessons", "Enseignements tirés", "Lessons learnt"),
            S("next_activities", "Plan de travail de la période suivante", "Work plan for the next period"),
            S("budget", "Informations financières", "Financial information"),
            ANNEX_LOGFRAME,
        ],
    ),
    _f(
        "echo",
        "Union européenne (aide humanitaire)",
        "Aide humanitaire de l'Union européenne : rapport intermédiaire",
        "EU humanitarian aid: interim report",
        [
            SUMMARY,
            T("needs", "Évolution des besoins et du contexte", "Evolution of needs and context"),
            S("results", "Objectif spécifique et résultats", "Specific objective and results"),
            S("tracking", "Indicateurs", "Indicators"),
            S("beneficiaries", "Bénéficiaires atteints", "Beneficiaries reached"),
            S("feedback", "Redevabilité envers les personnes touchées", "Accountability to affected people"),
            T("monitoring_text", "Suivi de l'action", "Monitoring of the action"),
            S("risks", "Risques et sécurité", "Risks and security"),
            VISIBILITY,
            S("budget", "Situation financière", "Financial situation"),
        ],
    ),
    _f(
        "usaid",
        "USAID",
        "USAID : rapport trimestriel de performance",
        "USAID: quarterly performance report",
        [
            T("summary", "Résumé exécutif", "Executive summary"),
            T("overview", "Présentation de l'activité", "Activity overview"),
            S("results", "Avancement de la mise en œuvre par résultat", "Implementation progress by result"),
            S("tracking", "Tableau de suivi des indicateurs de performance", "Indicator performance tracking table"),
            S("gaps", "Explication des écarts aux cibles", "Deviation narratives"),
            T("mel", "Activités de suivi, d'évaluation et d'apprentissage", "Monitoring, evaluation and learning"),
            CROSS,
            DIFFICULTIES,
            S("lessons", "Leçons apprises", "Lessons learned"),
            S("next_activities", "Activités prévues le trimestre suivant", "Planned activities for next quarter"),
            S("budget", "Résumé financier", "Financial summary"),
        ],
    ),
    _f(
        "afd",
        "Agence française de développement",
        "AFD : rapport d'exécution technique et financière",
        "AFD: technical and financial execution report",
        [
            SUMMARY,
            CONTEXT,
            S("results", "Avancement par composante et par résultat", "Progress by component and result"),
            S("tracking", "Indicateurs du cadre logique", "Logframe indicators"),
            S("activities", "Activités réalisées", "Activities carried out"),
            DIFFICULTIES,
            S("risks", "Suivi des risques", "Risk monitoring"),
            NEXT_STEPS,
            S("budget", "Exécution financière", "Financial execution"),
            FINANCE_TEXT,
        ],
    ),
    _f(
        "expertise_france",
        "Expertise France",
        "Expertise France : rapport d'activité",
        "Expertise France: activity report",
        [
            SUMMARY,
            S("activities", "Activités réalisées", "Activities carried out"),
            S("results", "Résultats obtenus", "Results achieved"),
            S("tracking", "Indicateurs", "Indicators"),
            S("risks", "Risques", "Risks"),
            S("next_activities", "Programmation de la période suivante", "Programming for the next period"),
            S("budget", "Suivi financier", "Financial follow-up"),
        ],
    ),
    _f(
        "world_bank",
        "Banque mondiale",
        "Banque mondiale : rapport d'avancement du projet",
        "World Bank: project progress report",
        [
            SUMMARY,
            S(
                "tracking",
                "Progrès vers l'objectif de développement et résultats intermédiaires",
                "Progress towards the PDO and intermediate results",
            ),
            S("results", "Avancement par composante", "Implementation progress by component"),
            T("safeguards", "Gestion environnementale et sociale", "Environmental and social management"),
            T("fiduciary", "Gestion financière et passation des marchés", "Financial management and procurement"),
            S("feedback", "Mécanisme de gestion des plaintes", "Grievance redress mechanism"),
            S("risks", "Risques", "Risks"),
            S("budget", "Décaissements et exécution", "Disbursements and execution"),
            NEXT_STEPS,
        ],
    ),
    _f(
        "afdb",
        "Banque africaine de développement",
        "BAD : rapport d'avancement trimestriel",
        "AfDB: quarterly progress report",
        [
            SUMMARY,
            S("tracking", "Progrès vers les objectifs : indicateurs", "Progress towards objectives: indicators"),
            S("results", "Exécution par composante", "Implementation by component"),
            T("procurement", "Passation des marchés", "Procurement"),
            S("budget", "Gestion financière", "Financial management"),
            T("safeguards", "Sauvegardes environnementales et sociales", "Environmental and social safeguards"),
            DIFFICULTIES,
            NEXT_STEPS,
        ],
    ),
    _f(
        "undp",
        "PNUD",
        "PNUD : rapport d'avancement",
        "UNDP: progress report",
        [
            T("summary", "Résumé exécutif", "Executive summary"),
            CONTEXT,
            S("results", "Résultats par produit", "Results by output"),
            S(
                "tracking",
                "Cadre de résultats et ressources : indicateurs",
                "Results and resources framework: indicators",
            ),
            PARTNERSHIPS,
            T("gender", "Égalité des genres", "Gender equality"),
            S("risks", "Risques et problèmes", "Risks and issues"),
            S("lessons", "Enseignements", "Lessons learned"),
            T("way_forward", "Perspectives", "Way forward"),
            S("budget", "Exécution financière", "Financial delivery"),
        ],
    ),
    _f(
        "unicef",
        "UNICEF",
        "UNICEF : rapport au donateur",
        "UNICEF: donor report",
        [
            T("summary", "Résumé exécutif", "Executive summary"),
            T("context", "Contexte stratégique", "Strategic context"),
            S("results", "Résultats obtenus", "Results achieved"),
            S("tracking", "Indicateurs", "Indicators"),
            S("budget", "Analyse financière", "Financial analysis"),
            T("future", "Plan de travail futur", "Future work plan"),
            T("story", "Témoignage", "Human interest story"),
            T("thanks", "Remerciements", "Expression of thanks"),
        ],
    ),
    _f(
        "wfp",
        "PAM",
        "PAM : rapport de projet",
        "WFP: project report",
        [
            SUMMARY,
            CONTEXT,
            S("beneficiaries", "Bénéficiaires", "Beneficiaries"),
            S("results", "Résultats : effets et produits", "Results: outcomes and outputs"),
            S("tracking", "Indicateurs", "Indicators"),
            T("cross_cutting", "Genre, protection et redevabilité", "Gender, protection and accountability"),
            S("feedback", "Redevabilité envers les populations touchées", "Accountability to affected populations"),
            PARTNERSHIPS,
            S("lessons", "Enseignements", "Lessons learned"),
            S("budget", "Ressources et dépenses", "Resources and expenditure"),
        ],
    ),
    _f(
        "unhcr",
        "HCR",
        "HCR : rapport d'avancement du partenaire",
        "UNHCR: partner progress report",
        [
            SUMMARY,
            T("population", "Populations concernées", "Persons of concern"),
            S("results", "Résultats par impact, effet et produit", "Results by impact, outcome and output"),
            S("tracking", "Indicateurs", "Indicators"),
            T("protection", "Protection", "Protection"),
            S("feedback", "Redevabilité envers les personnes touchées", "Accountability to affected people"),
            DIFFICULTIES,
            S("budget", "Exécution financière", "Financial execution"),
        ],
    ),
    _f(
        "unfpa",
        "FNUAP",
        "FNUAP : rapport d'avancement",
        "UNFPA: progress report",
        [
            SUMMARY,
            S("results", "Résultats", "Results"),
            S("tracking", "Indicateurs", "Indicators"),
            DIFFICULTIES,
            S("lessons", "Leçons apprises", "Lessons learned"),
            NEXT_STEPS,
            S("budget", "Exécution financière", "Financial execution"),
        ],
    ),
    _f(
        "who",
        "OMS",
        "OMS : rapport technique",
        "WHO: technical report",
        [
            SUMMARY,
            T("background", "Contexte", "Background"),
            S("results", "Avancement par livrable", "Progress by deliverable"),
            S("tracking", "Indicateurs", "Indicators"),
            DIFFICULTIES,
            S("lessons", "Enseignements", "Lessons learned"),
            NEXT_STEPS,
            S("budget", "Rapport financier", "Financial report"),
        ],
    ),
    _f(
        "global_fund",
        "Fonds mondial",
        "Fonds mondial : mise à jour sur les progrès",
        "Global Fund: progress update",
        [
            S(
                "tracking",
                "Cadre de performance : indicateurs et cibles",
                "Performance framework: indicators and targets",
            ),
            S("gaps", "Explication des écarts", "Explanation of deviations"),
            T("programme", "Gestion programmatique", "Programmatic management"),
            T("supply", "Gestion des achats et des stocks", "Procurement and supply management"),
            S("budget", "Rapport financier", "Financial report"),
            S("recommendations", "Suivi des actions de gestion", "Follow-up of management actions"),
            S("risks", "Risques", "Risks"),
        ],
    ),
    _f(
        "gavi",
        "Gavi",
        "Gavi : rapport de performance de la subvention",
        "Gavi: grant performance report",
        [
            SUMMARY,
            S("tracking", "Performance programmatique : indicateurs", "Programmatic performance: indicators"),
            S("results", "Avancement par objectif", "Progress by objective"),
            S("budget", "Performance financière", "Financial performance"),
            S("risks", "Risques", "Risks"),
            S("lessons", "Enseignements", "Lessons learned"),
            NEXT_STEPS,
        ],
    ),
    _f(
        "ifrc",
        "FICR",
        "FICR : rapport d'opération",
        "IFRC: operation report",
        [
            SUMMARY,
            T("situation", "Analyse de la situation", "Situation analysis"),
            S("results", "Mise en œuvre par secteur", "Implementation by sector"),
            S("tracking", "Indicateurs", "Indicators"),
            S("feedback", "Engagement communautaire et redevabilité", "Community engagement and accountability"),
            DIFFICULTIES,
            S("budget", "Rapport financier", "Financial report"),
        ],
    ),
    _f(
        "giz",
        "GIZ",
        "GIZ : rapport d'avancement",
        "GIZ: progress report",
        [
            SUMMARY,
            S("tracking", "Indicateurs de l'objectif du module", "Module objective indicators"),
            S("results", "Avancement des produits", "Progress of outputs"),
            S("risks", "Risques", "Risks"),
            CROSS,
            S("lessons", "Enseignements", "Lessons learned"),
            T("outlook", "Perspectives", "Outlook"),
            S("budget", "Situation financière", "Financial situation"),
        ],
    ),
    _f(
        "enabel",
        "Enabel",
        "Enabel : rapport de résultats",
        "Enabel: results report",
        [
            SUMMARY,
            S("results", "Progrès vers les résultats", "Progress towards results"),
            S("tracking", "Indicateurs", "Indicators"),
            S("risks", "Gestion des risques", "Risk management"),
            S("lessons", "Enseignements", "Lessons learned"),
            NEXT_STEPS,
            S("budget", "Exécution budgétaire", "Budget execution"),
        ],
    ),
    _f(
        "fcdo",
        "Royaume-Uni (FCDO)",
        "Royaume-Uni (FCDO) : revue annuelle",
        "UK (FCDO): annual review",
        [
            SUMMARY,
            S("results", "Progrès par produit", "Progress against outputs"),
            S("tracking", "Indicateurs du cadre logique", "Logframe indicators"),
            T("vfm", "Optimisation des ressources", "Value for money"),
            S("risks", "Risques", "Risks"),
            S("recommendations", "Recommandations et suites données", "Recommendations and follow-up"),
            S("lessons", "Enseignements", "Lessons"),
            S("budget", "Exécution financière", "Financial execution"),
        ],
    ),
    _f(
        "gates",
        "Fondation Gates",
        "Fondation Gates : rapport d'avancement de la subvention",
        "Gates Foundation: grant progress report",
        [
            SUMMARY,
            S("tracking", "Progrès vers les résultats et les jalons", "Progress against outcomes and milestones"),
            S("results", "Avancement par résultat", "Progress by result"),
            DIFFICULTIES,
            S("lessons", "Enseignements", "Lessons learned"),
            T("changes", "Changements dans le projet", "Changes to the project"),
            S("budget", "Rapport financier", "Financial report"),
        ],
    ),
    _f(
        "me_plan",
        "",
        "Plan de suivi et d'évaluation",
        "Monitoring and evaluation plan",
        [
            T(
                "introduction",
                "Introduction",
                "Introduction",
                "Objet du plan, projet, période couverte.",
                "Purpose of the plan, project, period covered.",
            ),
            S("logframe", "Cadre logique", "Logical framework"),
            S("pirs", "Fiches des indicateurs", "Indicator reference sheets"),
            S("calendar", "Calendrier de collecte des données", "Data collection calendar"),
            S("evaluations", "Évaluations prévues", "Planned evaluations"),
            T(
                "roles",
                "Rôles et responsabilités",
                "Roles and responsibilities",
                "Qui collecte, vérifie, valide, analyse et rapporte.",
                "Who collects, checks, validates, analyses and reports.",
            ),
            T("quality", "Qualité des données", "Data quality"),
            T("use", "Utilisation des données et apprentissage", "Data use and learning"),
        ],
    ),
    _f(
        "pirs",
        "",
        "Fiches des indicateurs",
        "Indicator reference sheets",
        [S("pirs", "Fiches des indicateurs", "Indicator reference sheets")],
    ),
]

BY_ID = {f["id"]: f for f in FORMATS}


def validate_custom(spec: Any) -> dict[str, Any]:
    """A format made by the user from scratch or from a provided one."""
    from .registers import _err, _obj, _text

    s = _obj(spec, "format")
    name = _text(s.get("name"), 200)
    if not name:
        raise _err("The format needs a name", "field_required", field="name")
    sections = []
    seen = set()
    for x in (s.get("sections") if isinstance(s.get("sections"), list) else [])[:60]:
        x = _obj(x, "section")
        kind = x.get("kind")
        if kind not in KINDS:
            raise _err("Unknown section kind", "invalid_params")
        key = _text(x.get("key"), 40) or kind
        if key in seen:
            key = f"{key}_{len(seen)}"
        seen.add(key)
        label = _text(x.get("label"), 200)
        if not label:
            raise _err("Each section needs a title", "field_required", field="label")
        sections.append({"key": key, "kind": kind, "fr": label, "en": label, "hint_fr": "", "hint_en": ""})
    if not sections:
        raise _err("Give at least one section", "field_required", field="sections")
    return {"name": name, "donor": _text(s.get("donor"), 200), "sections": sections}
