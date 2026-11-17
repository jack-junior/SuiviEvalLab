# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 GAYI Komi Selassi and SANOUSSI Moudjibou

"""Builds FICHE-RETOUR-PILOTE.docx, the feedback form of the 1.0 pilot test
(docs/guide/recette.md), to hand to each participant with the test kit.

    python tools/test-kit/pilot_form.py build/test-kit
"""

from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from docx.shared import Cm, Pt, RGBColor

KIT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("build/test-kit")
BLUE = RGBColor(0x1D, 0x4F, 0x91)

WEEKS = [
    (
        "Semaine 1 : paramétrer le projet",
        "Fiche du projet, calendrier, lieux, partenaires, désagrégations, cadre logique, indicateurs, "
        "cibles, plan de suivi, activités, budget, à partir du document de projet.",
        "Le projet est-il décrit sans recours à un autre outil ?",
    ),
    (
        "Semaine 2 : recevoir et valider quatre trimestres",
        "Saisie, canevas Excel envoyé à un partenaire, Kobo ou DHIS2 si disponible ; contrôles, "
        "validation, verrouillage.",
        "Le tableau de suivi est-il identique à votre fichier Excel habituel, chiffre par chiffre ?",
    ),
    (
        "Semaine 3 : tenir l'agenda et les registres",
        "Agenda et tâches pendant une semaine réelle ; retours et plaintes, recommandations, risques.",
        "L'agenda de l'application a-t-il remplacé celui que vous utilisez d'habitude ?",
    ),
    (
        "Semaine 4 : rapporter",
        "Rapport trimestriel au format de votre bailleur avec le modèle Word de votre organisation ; "
        "note de synthèse de plusieurs projets.",
        "Le rapport a-t-il pu être remis tel quel, ou avec des retouches de forme seulement ?",
    ),
]


def heading(doc: Document, text: str, level: int = 1) -> None:
    h = doc.add_heading(text, level)
    for r in h.runs:
        r.font.color.rgb = BLUE


def grid(doc: Document, head: list[str], rows: int, widths: list[float]) -> None:
    t = doc.add_table(rows=rows + 1, cols=len(head))
    t.style = "Table Grid"
    for i, h in enumerate(head):
        cell = t.rows[0].cells[i]
        cell.text = h
        cell.paragraphs[0].runs[0].font.bold = True
        for row in t.rows:
            row.cells[i].width = Cm(widths[i])
    for row in t.rows[1:]:
        row.height = Cm(1.2)


def main() -> None:
    KIT.mkdir(parents=True, exist_ok=True)
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)
    heading(doc, "SuiviEvalLab 1.0 : fiche de retour du test pilote", 0)
    doc.add_paragraph(
        "Une fiche par participant. Remplissez-la au fil des semaines et renvoyez-la à la fin du test. "
        "Le déroulement complet est décrit dans la documentation, chapitre « Test pilote »."
    )
    grid(doc, ["Participant", "Organisation", "Fonction", "Projet test"], 1, [4, 4, 4, 4.5])

    for title, work, question in WEEKS:
        heading(doc, title)
        doc.add_paragraph(work)
        doc.add_paragraph("Ce qui a fonctionné sans aide :")
        doc.add_paragraph("\n\n")
        doc.add_paragraph("Blocages (ce qui empêchait d'avancer) :")
        grid(doc, ["N°", "Écran et étapes", "Ce qui s'est passé", "Capture jointe"], 4, [1, 5, 8, 2.5])
        doc.add_paragraph()
        doc.add_paragraph("Écarts de chiffres avec votre fichier habituel :")
        grid(doc, ["Indicateur", "Période", "Votre fichier", "SuiviEvalLab"], 3, [6, 3, 3.5, 3.5])
        doc.add_paragraph()
        grid(doc, ["Temps passé", "Temps habituel pour le même travail"], 1, [8, 8.5])
        doc.add_paragraph()
        doc.add_paragraph(f"{question}   Oui / Non")

    heading(doc, "Travail en équipe (si vous en faites partie)")
    doc.add_paragraph(
        "Rôle tenu, façons d'échanger utilisées (paquets, dossier partagé, serveur), conflits rencontrés :"
    )
    doc.add_paragraph("\n\n")
    doc.add_paragraph("Toutes les copies avaient-elles les mêmes chiffres à la fin de la semaine ?   Oui / Non")

    heading(doc, "Conclusion")
    doc.add_paragraph(
        "L'outil peut-il remplacer vos fichiers et vos agendas habituels pour ce travail ?\n"
        "Oui      Oui, avec réserves      Non"
    )
    doc.add_paragraph("Pourquoi, et quelles réserves :")
    doc.add_paragraph("\n\n\n")
    out = KIT / "FICHE-RETOUR-PILOTE.docx"
    doc.save(str(out))
    print(out)


if __name__ == "__main__":
    main()
