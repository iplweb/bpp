Naprawiono renderowanie formularza zgłaszania publikacji
(``/zglos_publikacje/``) — stopka strony była "wciągana" do
wnętrza przycisku "następny krok" / "zakończ i wyślij do akceptacji".
Przyczyną były XHTML-owe samozamykające się ``<span class="fi-..."/>``
przy ikonach Foundation: minifier ``minify-html`` (zgodnie ze
specyfikacją HTML5) ignoruje ``/`` na elementach nie-void, więc span
pozostawał otwarty, a wraz z nim zjadał także zamykający ``</button>``,
co powodowało, że dalsza zawartość strony — łącznie ze stopką — stawała
się dzieckiem przycisku. Spany ikon zamieniono na pełną parę
``<span></span>``.
