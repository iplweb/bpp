Naprawiono cichy ReferenceError w produkcyjnym bundlu JS: funkcja
``dalLoadLanguage`` (polskie tłumaczenia autouzupełniania django-autocomplete-light /
select2) była usuwana przez tree-shaking esbuilda, przez co pola autouzupełniania
traciły polskie komunikaty. Loader języka jest teraz jawnie eksportowany na
``window`` w lokalnym wrapperze odpornym na tree-shaking.
