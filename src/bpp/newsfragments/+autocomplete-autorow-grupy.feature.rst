Autocomplete autorów w panelu admina pokazuje teraz wszystkich autorów,
zgrupowanych w trzy sekcje (``optgroup``) wyróżniające ich powiązanie
z aktualnie obsługiwaną uczelnią:

* „Autorzy z naszej uczelni” — autorzy, których ``aktualna_jednostka``
  należy do uczelni rozwiązanej z bieżącej domeny
  (``Uczelnia.objects.get_for_request``).
* „Autorzy powiązani historycznie z naszą uczelnią” — autorzy z dowolnym
  wpisem ``Autor_Jednostka`` w naszej uczelni, niezależnie od ``aktualna_jednostka``.
* „Autorzy zewnętrzni” — pozostali (np. z innych uczelni federacji
  multi-hosted lub bez powiązania z jednostką).

Wcześniej autocomplete twardo filtrował wyłącznie autorów z aktualną
jednostką w bieżącej uczelni, co uniemożliwiało wybranie wieloetatowca,
byłego pracownika ani autora z uczelni partnerskiej.
