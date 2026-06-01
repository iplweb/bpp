Naprawiono rozbijanie dwukolumnowego układu strony rekordu przez
treść streszczenia. Streszczenia importowane z zewnętrznych źródeł
zawierają operatory porównania wpisane wprost w tekst (np.
``<30 IU/dL``, ``ct<or ≥15K``, ``>= 1%``). Pojedynczy znak ``<`` bez
zamykającego ``>`` był traktowany przez minifikator HTML jak otwarcie
znacznika, który połykał dalszy markup (w tym zamykające znaczniki
prawej kolumny) — cała strona zlewała się do jednej kolumny, a tekst
streszczenia wyświetlał się jako posortowana sieczka słów.

Streszczenia są teraz renderowane przez filtr ``|safe_streszczenie``,
który escape'uje gołe operatory ``<``/``>`` i sanityzuje pozostały
markup (usuwa m.in. znaczniki JATS z importu Crossref oraz ewentualny
kod XSS), oddając poprawny, zbalansowany HTML. Dotyczy to widoku
rekordu oraz listy najnowszych streszczeń na stronie uczelni.
