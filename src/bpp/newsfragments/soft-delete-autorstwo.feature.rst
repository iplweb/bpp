Wewnętrzny fundament pod usuwanie „miękkie" (soft-delete) powiązań autor-
-publikacja: trzy tabele przypisań autorstwa (wydawnictwa ciągłe, zwarte,
patenty) zyskały znaczniki kasowania/przywracania zamiast trwałego
usuwania wiersza. Skasowane przypisania znikają też z widoków źródłowych i
z materializowanego cache'u bibliografii, więc nie pokazują się na stronach
publikacji, w liczbie publikacji autora, w podpowiedziach wyszukiwarki,
w eksporcie BibTeX, w listach panelu administracyjnego ani w zestawieniach
oświadczeń wysyłanych do PBN.
Skasowanie i przywrócenie przypisania aktualizuje jego znacznik „ostatnio
zmieniony", dzięki czemu systemy pobierające dane przyrostowo widzą taką
operację jako zwykłą modyfikację rekordu.
Zmiana jest na razie wewnętrzna i niewidoczna dla użytkowników —
pełne wsparcie (panel administracyjny, przywracanie) wdrażają kolejne etapy.
