from dataclasses import dataclass


@dataclass(frozen=True)
class Metryka:
    slug: str
    field_name: str
    label: str
    is_quartile: bool
    recalculates_disciplines: bool
    decimal_places: int


METRYKI: list[Metryka] = [
    Metryka("if", "impact_factor", "Impact Factor", False, False, 3),
    Metryka("mnisw", "punkty_kbn", "Punkty MNiSW", False, True, 2),
    Metryka("kw_scopus", "kwartyl_w_scopus", "Kwartyl Scopus", True, False, 0),
    Metryka("kw_wos", "kwartyl_w_wos", "Kwartyl WoS", True, False, 0),
]

METRYKI_BY_SLUG: dict[str, Metryka] = {m.slug: m for m in METRYKI}
DEFAULT_METRYKA: Metryka = METRYKI[0]
METRYKA_CHOICES: list[tuple[str, str]] = [(m.slug, m.label) for m in METRYKI]
