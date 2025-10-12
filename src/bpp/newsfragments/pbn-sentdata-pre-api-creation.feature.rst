Poprawiono system śledzenia wysyłania danych do PBN (SentData).

* Dodano tworzenie rekordów SentData PRZED wywołaniem API PBN, co zapewnia pełny audyt prób wysyłki.
* Wprowadzono nowe pola w modelu SentData:
  - ``submitted_successfully`` - flaga wskazująca czy wywołanie API zakończyło się sukcesem
  - ``submitted_at`` - timestamp momentu wysyłki danych
  - ``api_response_status`` - pełna odpowiedź z API PBN (jako TextField)
* Zmieniono logikę tworzenia rekordów tak, aby aktualizować istniejące rekordy zamiast tworzyć nowe przy próbach ponowienia, co zapobiega niekontrolowanemu wzrostowi bazy danych.
* Dodano nowe metody w SentDataManager:
  - ``create_or_update_before_upload()`` - tworzy lub aktualizuje rekord przed API
  - ``check_if_upload_needed()`` - sprawdza czy wysyłka jest potrzebna (tylko na podstawie udanych wysyłek)
  - ``mark_as_successful()`` - oznacza rekord jako udany po sukcesie API
  - ``mark_as_failed()`` - oznacza rekord jako nieudany z informacjami o błędzie
* Zapewniono kompatybilność wsteczną - istniejące metody ``check_if_needed()`` i ``updated()`` zostały zachowane.
* Poprawiono logikę ponawiania prób przy błędach walidacji API, przywracając ``time.sleep(0.5)`` między próbami.

Dzięki tym zmianom system teraz tworzy kompletne ślady audytowe dla wszystkich prób wysyłki do PBN (zarówno do API publikacji jak i repozytorium), jednocześnie utrzymując czystość i wydajność bazy danych.
