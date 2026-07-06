Admin ``Wydawnictwo ciągłe`` i ``Wydawnictwo zwarte`` ma nowy filtr „PBN:
status" — pozwala wyłapać rekordy powiązane z pracą skasowaną w PBN
(``DELETED``), aktywną (``ACTIVE``) albo bez powiązania. To samo zawężenie
działa też w wyszukiwaniu DjangoQL: ``pbn_uid.status = "DELETED"``.
