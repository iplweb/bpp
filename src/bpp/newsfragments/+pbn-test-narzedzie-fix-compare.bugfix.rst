Poprawka w narzędziu CLI ``pbn_test_wysylka_interaktywna``:

- krok porównania oświadczeń (KROK 6/8) używał lokalnego cache'a
  ``OswiadczenieInstytucji`` (snapshot z poprzedniej synchronizacji
  PBN) jako reprezentanta „stanu BPP", co powodowało fałszywą
  identyczność po zmianach w rekordzie — skasowaniu autora,
  zmianie/wypięciu dyscypliny lub innej edycji ``Wydawnictwo_*_Autor``
  (cache nie był re-synchronizowany, pokazywał stare 3 oświadczenia
  nawet po faktycznym zmniejszeniu intencji BPP do 2). Narzędzie
  teraz porównuje **intencję BPP na żywo** — to co by wygenerował
  ``WydawnictwoPBNAdapter.pbn_get_api_statements()`` gdyby wysyłać
  teraz — z aktualnym stanem PBN. Dodatkowo KROK 1/8 pokazuje zarówno
  cache jak i intencję żywą, żeby od razu widać było rozjazd.
- narzędzie zawsze pyta osobno o DELETE oświadczeń i osobno o POST
  oświadczeń, także gdy porównanie zwróciło identyczność —
  użytkownik może wymusić operację np. dla empirycznego sprawdzenia
  reakcji PBN (wcześniej flow kończył się wczesnym ``return`` po
  identyczności bez opcji kontynuacji). Domyślna wartość pytania
  zależy od wyniku porównania: „identyczne" → default ``n``,
  „różnice" → default ``t``.
