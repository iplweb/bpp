Trigger odświeżający tabele cache (``bpp_rekord_mat`` /
``bpp_autorzy_mat``) działa wydajniej i poprawniej: edycja publikacji
nie kasuje już i nie wstawia od nowa wszystkich wierszy autorów
(czysty upsert zamiast DELETE z kaskadą FK), masowe operacje nie
zużywają subtransakcji per wiersz, zmiana autora wpisu „in-place"
poprawnie aktualizuje cache, a usunięcie jednej z dwóch ról tego
samego autora (np. autor + redaktor) nie usuwa już obu wierszy
z cache autorów.
