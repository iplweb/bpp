Ustabilizowano test fazy general deduplikatora autorów
(``test_general_finds_pair_with_unicode_hyphen_variant``), który flakował
pod ``pytest-xdist``/shardingiem. Faza general skanuje całą tabelę autorów,
więc ambient rekordy scommitowane przez sąsiednie testy (o pospolitych
nazwiskach jak „Nowak"/„Kowalski") doczepiały się do klastra i przejmowały
rolę rekordu głównego, psując asercję na dokładnej liczbie i tożsamości pary.
Test sprawdza teraz wyłącznie własną inwariantę: po normalizacji myślnika
Unicode obaj autorzy trafiają do tego samego klastra duplikatów.
