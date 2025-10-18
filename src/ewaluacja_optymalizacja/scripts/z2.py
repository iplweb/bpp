# pip install ortools
from dataclasses import dataclass

from ortools.sat.python import cp_model

# We'll scale slot numbers by 10 so 0.5 -> 5, 0.3 -> 3 (integers for CP-SAT)
SCALE = 10


@dataclass(frozen=True)
class Pub:
    id: str
    author: str
    kind: str  # "article" | "monography"
    points: int
    base_slots: float  # e.g., 1.0, 0.5, 0.3


def slot_units(p: Pub) -> int:
    return int(round(p.base_slots * SCALE))


def is_low_mono(p: Pub) -> bool:
    return p.kind == "monography" and p.points < 200


# -------- sample data (edit freely) ------------------------------------------
pubs: list[Pub] = [
    Pub("A1", "Alice", "article", 200, 1.0),
    Pub("A2", "Alice", "article", 140, 1.0),
    Pub("A3", "Alice", "article", 75, 0.5),
    Pub("A4", "Alice", "monography", 120, 1.0),  # low-point mono
    Pub("B1", "Bob", "monography", 200, 1.0),
    Pub("B2", "Bob", "article", 150, 1.0),
    Pub("B3", "Bob", "article", 50, 0.3),
    Pub("C1", "Cara", "monography", 110, 1.0),  # low-point mono
    Pub("C2", "Cara", "article", 200, 1.0),
    Pub("C3", "Cara", "article", 75, 0.5),
]
authors = sorted({p.author for p in pubs})

# -------- model --------------------------------------------------------------
m = cp_model.CpModel()
y = {p.id: m.NewBoolVar(f"y_{p.id}") for p in pubs}

# Objective: maximize total points
m.Maximize(sum(p.points * y[p.id] for p in pubs))

# Per-author constraints
MAX_SLOTS_TOTAL = int(4.0 * SCALE)
MAX_SLOTS_MONO = int(2.0 * SCALE)

for a in authors:
    # total slots ≤ 4.0
    m.Add(
        sum(slot_units(p) * y[p.id] for p in pubs if p.author == a) <= MAX_SLOTS_TOTAL
    )
    # monography slots ≤ 2.0
    m.Add(
        sum(
            slot_units(p) * y[p.id]
            for p in pubs
            if p.author == a and p.kind == "monography"
        )
        <= MAX_SLOTS_MONO
    )

# Institution quota: low-point monographies ≤ 20% of all selected works (by count)
low_mono_count = sum(y[p.id] for p in pubs if is_low_mono(p))
total_count = sum(y[p.id] for p in pubs)
# Linearized: 5 * low_mono_count ≤ total_count (handles total_count=0 ⇒ trivially satisfied)
m.Add(5 * low_mono_count <= total_count)

# -------- solve --------------------------------------------------------------
solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = 5.0
status = solver.Solve(m)
print("Status:", solver.StatusName(status))
print("Total points:", int(solver.ObjectiveValue()))

# Report
by_author: dict[str, list[Pub]] = {a: [] for a in authors}
for p in pubs:
    if solver.Value(y[p.id]) == 1:
        by_author[p.author].append(p)

for a in authors:
    chosen = by_author[a]
    total_slots = sum(p.base_slots for p in chosen)
    mono_slots = sum(p.base_slots for p in chosen if p.kind == "monography")
    pts = sum(p.points for p in chosen)
    print(
        f"\nAuthor {a}: points={pts}, slots={total_slots:.1f} (mono={mono_slots:.1f})"
    )
    for p in chosen:
        tag = "LOW-MONO" if is_low_mono(p) else p.kind
        print(f"  - {p.id}: {tag}, pts={p.points}, slots={p.base_slots}")

sel_total = sum(solver.Value(y[p.id]) for p in pubs)
sel_low = sum(solver.Value(y[p.id]) for p in pubs if is_low_mono(p))
share = (100.0 * sel_low / sel_total) if sel_total > 0 else 0.0
print(
    f"\nInstitution: selected {sel_total} works; low-point monographies = {sel_low} ({share:.1f}% ≤ 20%)"
)
