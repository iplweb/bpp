"""
Stałe używane w module deduplikator_autorow.
"""

# Stałe reprezentujące maksymalną i minimalną możliwą pewność duplikatu
# Obliczone na podstawie wszystkich kryteriów oceny w analiza_duplikatow()

# Maksymalna teoretyczna pewność (optymalne warunki):
# +10 (≤5 publikacji) +15 (brak tytułu) +50 (identyczny ORCID) +40 (identyczne nazwisko)
# +50 (pełna zamiana imienia z nazwiskiem)
# +90 (3 identyczne imiona: 30*3) +45 (3 podobne imiona: 15*3) +15 (3 inicjały: 5*3)
# +10 (brak imion) +20 (wspólne lata publikacji)
# = +345 (w praktyce rzadko przekracza 250 ze względu na wzajemne wykluczanie się warunków)
MAX_PEWNOSC = 250

# Minimalna teoretyczna pewność (najgorsze warunki):
# -30 (więcej publikacji niż główny) -15 (różny tytuł) -50 (różny ORCID)
# -20 (duża odległość lat publikacji)
# = -115
MIN_PEWNOSC = -115
