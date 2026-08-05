Naprawiono błąd, przez który jednostki ukryte (``widoczna=False``, m.in.
"Obca jednostka" skupiająca autorów obcych) zwracały 404 przez REST API,
psując eksport bibliografii u konsumentów podążających za hiperłączami z
autorów. Widoczność nie bramkuje już API — o dostępności jednostki przez API
decyduje wyłącznie nowe pole ``nie eksportuj przez API`` (domyślnie wyłączone,
czyli wszystkie jednostki są eksportowane). Redaktor może nim jawnie wykluczyć
wybraną jednostkę z API.
