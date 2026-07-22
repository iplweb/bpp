Usunięto niestabilność testów integracji jednostek importu pracowników przy
uruchamianiu współbieżnym (pytest-xdist, sharding CI): sąsiedni test mógł
zostawić w bazie zacommitowaną drugą uczelnię (ambient-data), przez co
``Uczelnia.objects.get_single_uczelnia_or_none()`` degradował do ``None`` i
tryb „brak" nie tworzył jednostki. Testy utwardzono, gwarantując dokładnie
jedną uczelnię (zielone w izolacji, wcześniej czerwone w niektórych układach
shardów).
