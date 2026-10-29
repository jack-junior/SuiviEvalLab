"""Demo data: fictional education project.

Generated deterministically so results are identical on every machine.
"""

from __future__ import annotations

import random

import polars as pl


def girls_6_11(seed: int = 2026) -> pl.DataFrame:
    """612 girls aged 6 to 11, with zone, village, weight and school attendance."""
    rng = random.Random(seed)
    rows = []
    villages = [f"V{i:02d}" for i in range(1, 37)]
    for i in range(612):
        village = villages[i % len(villages)]
        zone = "Urbaine" if int(village[1:]) <= 12 else "Rurale"
        p = 0.725 if zone == "Urbaine" else 0.579
        rows.append(
            {
                "id_menage": f"M{i + 1:04d}",
                "village": village,
                "zone": zone,
                "age": rng.randint(6, 11),
                "poids": round(rng.uniform(0.8, 1.3), 3),
                "scolarise": "Oui" if rng.random() < p else "Non",
            }
        )
    return pl.DataFrame(rows)
