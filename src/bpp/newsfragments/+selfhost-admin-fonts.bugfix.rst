Panel administracyjny nie pobiera już fontów z ``fonts.googleapis.com``
przy każdym wyświetleniu strony. Rodziny używane przez przełącznik
motywów (Inter, Open Sans, Roboto, Lato, Source Sans Pro) są teraz
hostowane lokalnie jako pliki ``.woff2`` w ``static/bpp/fonts/``
(podzbiory ``latin`` i ``latin-ext``, z polskimi znakami diakrytycznymi).

Usuwa to zewnętrzną zależność sieciową: przeglądarka nie łączy się już z
serwerami Google, a awaria DNS nie blokuje ładowania panelu (wcześniej
``@import`` z Google potrafił wieszać renderowanie i powodować timeouty
testów przeglądarkowych). Ładowanie admina jest też szybsze i nie
wycieka informacji o korzystaniu z systemu do podmiotów trzecich.
