def pbn_token_aktualny(request):
    if not request.user.is_authenticated:
        return {}

    pbn_user = request.user.get_pbn_user()

    if not pbn_user.pbn_token_possibly_valid():
        from pbn_api.models import PBN_Export_Queue

        cnt = PBN_Export_Queue.objects.filter(
            zamowil=request.user, zakonczono_pomyslnie=None
        ).count()

        # Jest zalogowany, ma rekordy, nie ma tokena z PBN
        if cnt:

            from django.urls import reverse

            from django.contrib import messages

            if pbn_user.pk == request.user.pk:
                messages.info(
                    request,
                    f"W kolejce na wysłanie do PBN czeka {cnt} wyedytowanych przez Ciebie rekord(y/ów), ale "
                    f"nie jesteś zalogowany/a do PBN. <a href={reverse('pbn_api:authorize')}>Kliknij tutaj, aby "
                    f"autoryzować się w PBN</a>. ",
                )
            else:
                messages.info(
                    request,
                    f"W kolejce na wysłanie do PBN czeka {cnt} wyedytowanych przez Ciebie rekord(y/ów), ale "
                    f"{pbn_user.username}, z którego konta wysyłasz do PBNu, nie jesteś zalogowany/a do PBN. "
                    f"Przypomij temu użytkownikowy, aby dokonał autoryzacji. ",
                )

    return {}
