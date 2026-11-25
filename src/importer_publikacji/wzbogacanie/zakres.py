"""Zakres uczelni dla wzbogacania rekordu (instalacja wielouczelniana)."""


def w_zakresie_uczelni(request, rekord) -> bool:
    """Czy użytkownik z bieżącej domeny może wzbogacać ``rekord``.

    Formularz publikacji w module redagowania nie zawęża rekordów do uczelni,
    ale wzbogacanie zmienia rekord hurtem z danych zewnętrznych — stosujemy tę
    samą regułę przynależności co API i wyszukiwarka
    (``scope_publikacje_do_uczelni``): praca należy do uczelni, gdy
    którakolwiek jednostka na jej autorstwach należy do tej uczelni.

    Dozwolone także: superużytkownik, instalacja z jedną uczelnią (reguła
    jest wtedy no-op) oraz rekord BEZ żadnego autorstwa — nie należy jeszcze
    do nikogo, a właśnie jemu dodaje się brakujących autorów."""
    from bpp.models import Uczelnia
    from bpp.util.uczelnia_scope import scope_publikacje_do_uczelni

    if request.user.is_superuser:
        return True
    uczelnia = Uczelnia.objects.get_for_request(request)
    wiersz = type(rekord)._base_manager.filter(pk=rekord.pk)
    if scope_publikacje_do_uczelni(wiersz, uczelnia).exists():
        return True
    return not rekord.autorzy_set.exists()
