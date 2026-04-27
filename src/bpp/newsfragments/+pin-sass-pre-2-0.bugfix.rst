Przypięto wersję ``sass`` do ``~1.99.0`` w ``package.json`` zamiast
``^1.91.0``. Powód: blokada przed niekontrolowanym podniesieniem do
Sass 2.0 (które przerobi ``@import`` z deprecation warning na twardy
błąd kompilacji) oraz przed minor bumps (np. 1.100.x), które mogą
eskalować nowe kategorie deprecation warnings. Świadomy upgrade
wymaga teraz ręcznej zmiany pinu i przeglądu konsekwencji.
