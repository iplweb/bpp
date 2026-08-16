Kasowanie sesji importu PBN nie jest już blokowane komunikatem o braku
uprawnień do usunięcia wpisów dziennika importu. Django sprawdza uprawnienie do
usunięcia każdego obiektu kasowanego kaskadowo, a admin dziennika odmawiał go
bezwarunkowo — również superuserowi — więc nieusuwalna była w praktyce każda
sesja, która się wykonała, bo każdy import wpisy dziennika produkuje. Dziennik
nadal pozostaje niepodrabialny: nie można dopisać do niego wpisu ani zmienić
istniejącego, a ginie wyłącznie razem ze swoją sesją.
