"""Example project built on real data: access to education in Iraq, 2019 and 2020.

The two datasets are extracts of the REACH Iraq Multi-Cluster Needs Assessment
(rounds VII and VIII, CC BY 4.0, see examples/README.md). 2019 plays the role of
the baseline and 2020 of the endline of a fictional education project. The
results framework and the targets are illustrative; the data are real.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

EXAMPLES = Path(__file__).resolve().parent / "examples"

TEXT = {
    "fr": {
        "impact": "Les enfants des familles déplacées et retournées accèdent à une éducation de base",
        "o1": "L'accès physique aux écoles s'améliore près des lieux de vie",
        "o2": "Les familles ne retirent plus leurs enfants de l'école pour faire face aux difficultés",
        "p11": "Des salles de classe sont réhabilitées près des sites de retour",
        "a111": "Réhabiliter 40 salles de classe dans 12 écoles primaires",
        "a112": "Ouvrir 6 classes temporaires dans les zones sans école à moins de 2 km",
        "p21": "Les familles vulnérables reçoivent une aide en espèces liée à la scolarité",
        "a211": "Verser une aide trimestrielle à 1 500 familles avec enfants scolarisés",
        "i1": "Ménages ayant une école primaire à moins de 2 km",
        "i1d": "Part des ménages déclarant une école primaire à moins de 2 km de leur logement, parmi les ménages ayant répondu.",
        "i2": "Ménages ayant une école secondaire à moins de 2 km",
        "i2d": "Part des ménages déclarant une école secondaire à moins de 2 km de leur logement, parmi les ménages ayant répondu.",
        "i3": "Ménages ayant retiré des enfants de l'école pour faire face au manque de ressources",
        "i3d": "Part des ménages ayant retiré des enfants de l'école au cours des 30 derniers jours comme stratégie d'adaptation, parmi les ménages concernés.",
        "source": "Enquête ménages MCNA (REACH)",
        "d2019": "Enquête de référence 2019 (MCNA VII)",
        "d2020": "Enquête de fin de projet 2020 (MCNA VIII)",
        "r_groups": "Garder seulement les déplacés hors camp et les retournés, seuls groupes enquêtés en 2020",
        "r_dk": "« Ne sait pas » n'est pas une distance : valeur manquante",
        "r_na": "Ménages sans enfant d'âge scolaire : non concernés",
        "name": "Accès à l'éducation en Irak (exemple, données MCNA 2019 et 2020)",
        "attribution": "REACH Initiative, Iraq Multi-Cluster Needs Assessment {round}, Humanitarian Data Exchange, licence CC BY 4.0. Extrait de colonnes, valeurs inchangées.",
    },
    "en": {
        "impact": "Children of displaced and returnee families access basic education",
        "o1": "Physical access to schools improves near where families live",
        "o2": "Families no longer withdraw their children from school to cope with hardship",
        "p11": "Classrooms are rehabilitated near return areas",
        "a111": "Rehabilitate 40 classrooms in 12 primary schools",
        "a112": "Open 6 temporary classes in areas without a school within 2 km",
        "p21": "Vulnerable families receive cash assistance linked to schooling",
        "a211": "Pay quarterly assistance to 1,500 families with children in school",
        "i1": "Households with a primary school within 2 km",
        "i1d": "Share of households reporting a primary school within 2 km of their home, among households who answered.",
        "i2": "Households with a secondary school within 2 km",
        "i2d": "Share of households reporting a secondary school within 2 km of their home, among households who answered.",
        "i3": "Households that withdrew children from school to cope with a lack of resources",
        "i3d": "Share of households that withdrew children from school in the last 30 days as a coping strategy, among households concerned.",
        "source": "MCNA household survey (REACH)",
        "d2019": "Baseline survey 2019 (MCNA VII)",
        "d2020": "Endline survey 2020 (MCNA VIII)",
        "r_groups": "Keep only out-of-camp IDPs and returnees, the only groups surveyed in 2020",
        "r_dk": '"Do not know" is not a distance: missing value',
        "r_na": "Households without school-age children: not concerned",
        "name": "Access to education in Iraq (example, MCNA 2019 and 2020 data)",
        "attribution": "REACH Initiative, Iraq Multi-Cluster Needs Assessment {round}, Humanitarian Data Exchange, licence CC BY 4.0. Column extract, values unchanged.",
    },
}


# Labels of the example columns. The English wording comes from the MCNA
# questionnaires (sheet "MCNA VII Questionnaire"); the French is a translation.
# They are stored exactly like labels typed by a user in the Columns tab.
GOVERNORATES = {
    "al.anbar": "Al-Anbar",
    "al.basrah": "Al-Basrah",
    "al.najaf": "Al-Najaf",
    "al.qadissiya": "Al-Qadissiya",
    "al.sulaymaniyah": "Al-Sulaymaniyah",
    "babil": "Babil",
    "baghdad": "Baghdad",
    "diyala": "Diyala",
    "duhok": "Duhok",
    "erbil": "Erbil",
    "kerbala": "Kerbala",
    "kirkuk": "Kirkuk",
    "maysan": "Maysan",
    "ninewa": "Ninewa",
    "salah.al.din": "Salah Al-Din",
    "thi.qar": "Thi-Qar",
    "wassit": "Wassit",
}
PLACE = {
    "within_2km": ("À moins de 2 km", "Within 2 km"),
    "between_2_5": ("Entre 2 et 5 km", "Between 2 and 5 km"),
    "more_than5kmaway": ("À plus de 5 km", "More than 5 km"),
    "none": ("Aucune école accessible", "None that the household can access"),
    "do_not_know": ("Ne connaît pas d'école en fonctionnement", "Does not know of a functioning school"),
}
LABELS = {
    "population_group": (
        ("Groupe de population", "Population group"),
        {
            "idp_out_camp": ("Déplacés hors camp", "IDPs out of camp"),
            "idp_in_camp": ("Déplacés en camp", "IDPs in camp"),
            "returnee": ("Retournés", "Returnees"),
            "host": ("Communauté hôte", "Host community"),
        },
    ),
    "governorate_mcna": (("Gouvernorat", "Governorate"), {k: (v, v) for k, v in GOVERNORATES.items()}),
    "district": (("District", "District"), {}),
    "tot_child": (("Nombre d'enfants dans le ménage", "Number of children in the household"), {}),
    "primary_school_place": (
        (
            "Distance de l'école primaire en fonctionnement la plus proche",
            "How far is the closest functioning primary school",
        ),
        PLACE,
    ),
    "secondary_school_place": (
        (
            "Distance de l'école secondaire en fonctionnement la plus proche",
            "How far is the closest functioning secondary school",
        ),
        PLACE,
    ),
    "child_dropout_school": (
        (
            "Enfants retirés de l'école pour faire face au manque de ressources (30 derniers jours)",
            "Children dropout from school (last 30 days)",
        ),
        {
            "yes": ("Oui", "Yes"),
            "no_already_did": ("Non, déjà fait et plus possible", "No, because we already did it"),
            "no_nobody_in_hh_did": ("Non, personne dans le ménage", "No, nobody in the household did"),
            "not_applicable": ("Non concerné (pas d'enfant)", "Not applicable"),
        },
    ),
    "weights": (("Poids de sondage", "Sampling weight"), {}),
}


def _set_example_labels(svc: Any, dataset_id: str) -> None:
    columns = {c["name"] for c in svc.dataset_spec(dataset_id)["columns"]}
    for column, ((fr_label, en_label), values) in LABELS.items():
        if column not in columns:
            continue
        for lang, idx, text in (("fr", 0, fr_label), ("en", 1, en_label)):
            svc.set_labels(
                {
                    "id": dataset_id,
                    "column": column,
                    "lang": lang,
                    "label": text,
                    "values": {code: pair[idx] for code, pair in values.items()},
                }
            )


def fill_example(svc: Any, lang: str = "fr") -> None:
    t = TEXT.get(lang, TEXT["fr"])
    p = svc.project
    p.rename(t["name"])

    impact = p.add_node(None, t["impact"])["id"]
    o1 = p.add_node(impact, t["o1"])["id"]
    o2 = p.add_node(impact, t["o2"])["id"]
    p11 = p.add_node(o1, t["p11"])["id"]
    p.add_node(p11, t["a111"])
    p.add_node(p11, t["a112"])
    p21 = p.add_node(o2, t["p21"])["id"]
    p.add_node(p21, t["a211"])

    common = {"unit": "percent", "disaggregation": "population_group", "source": t["source"]}
    svc.save_indicator(
        {
            "node_id": o1,
            "indicator": {
                **common,
                "name": t["i1"],
                "definition": t["i1d"],
                "direction": "increase",
                "column": "primary_school_place",
                "success_values": ["within_2km"],
                "target": 0.9,
            },
        }
    )
    svc.save_indicator(
        {
            "node_id": o1,
            "indicator": {
                **common,
                "name": t["i2"],
                "definition": t["i2d"],
                "direction": "increase",
                "column": "secondary_school_place",
                "success_values": ["within_2km"],
                "target": 0.85,
            },
        }
    )
    svc.save_indicator(
        {
            "node_id": o2,
            "indicator": {
                **common,
                "name": t["i3"],
                "definition": t["i3d"],
                "direction": "decrease",
                "column": "child_dropout_school",
                "success_values": ["yes"],
                "target": 0.02,
            },
        }
    )

    design = {"weights": "weights", "strata": ["population_group", "governorate_mcna"], "cluster": None}
    for file, name, round_, id_col, round_label in (
        ("mcna_irak_2019.xlsx", t["d2019"], "baseline", "X_uuid", "VII (2019)"),
        ("mcna_irak_2020.xlsx", t["d2020"], "endline", "hh_id", "VIII (2020)"),
    ):
        created = svc.import_dataset(
            {
                "path": str(EXAMPLES / file),
                "name": name,
                "round": round_,
                "sheet": "Donnees menages",
                "design": design,
                "id_column": id_col,
                "attribution": t["attribution"].format(round=round_label),
            }
        )["created"]
        rules = [
            {"kind": "duplicates", "columns": [id_col], "note": ""},
            {
                "kind": "recode",
                "column": "primary_school_place",
                "from": ["do_not_know"],
                "to": None,
                "note": t["r_dk"],
            },
            {
                "kind": "recode",
                "column": "secondary_school_place",
                "from": ["do_not_know"],
                "to": None,
                "note": t["r_dk"],
            },
            {
                "kind": "recode",
                "column": "child_dropout_school",
                "from": ["not_applicable"],
                "to": None,
                "note": t["r_na"],
            },
        ]
        if round_ == "baseline":
            rules.insert(
                1,
                {
                    "kind": "exclude",
                    "column": "population_group",
                    "values": ["idp_in_camp", "host"],
                    "note": t["r_groups"],
                },
            )
        for rule in rules:
            svc.add_rule({"dataset_id": created, "rule": rule})
        _set_example_labels(svc, created)
