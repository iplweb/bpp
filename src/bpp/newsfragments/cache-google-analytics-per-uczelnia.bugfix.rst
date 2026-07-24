Naprawiono wyciek identyfikatora Google Analytics między uczelniami w
instalacjach wielo-uczelnianych. Snippet GA był cache'owany w szablonie pod
globalnym kluczem, mimo że ``GOOGLE_ANALYTICS_PROPERTY_ID`` jest ustawiany
per-uczelnia — pierwszy odwiedzający jednej uczelni „rozgrzewał" fragment
swoim identyfikatorem, a przez kolejną godzinę goście pozostałych uczelni
dostawali cudzy snippet, przez co ich ruch raportował się do konta Google
innej instytucji. Fragment nie jest już cache'owany.
