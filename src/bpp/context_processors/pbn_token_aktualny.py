def pbn_token_aktualny(request):
    if not request.user.is_authenticated:
        return {}

    pbn_user = request.user.get_pbn_user()

    if not pbn_user.pbn_token_possibly_valid():
        from pbn_export_queue.models import PBN_Export_Queue

        cnt = PBN_Export_Queue.objects.filter(
            zamowil=request.user, zakonczono_pomyslnie=None
        ).count()

        # Jest zalogowany, ma rekordy, nie ma tokena z PBN
        if cnt:
            from django.contrib import messages
            from django.urls import reverse
            from django.utils.html import format_html

            # Check if similar message already exists (ignoring the count value)
            existing_messages = messages.get_messages(request)
            has_similar_message = False

            for msg in existing_messages:
                msg_text = str(msg)
                # Check for the key parts of the message, ignoring the count
                if (
                    "W kolejce na wysłanie do PBN czeka" in msg_text
                    and "wyedytowanych przez Ciebie rekord" in msg_text
                ):
                    has_similar_message = True
                    break

            # Mark messages as used=False to keep them in the queue
            existing_messages.used = False

            if not has_similar_message:
                if pbn_user.pk == request.user.pk:
                    authorize_url = reverse("pbn_api:authorize")
                    messages.info(
                        request,
                        format_html(
                            "W kolejce na wysłanie do PBN czeka {} wyedytowanych "
                            "przez Ciebie rekord(y/ów), ale nie jesteś "
                            'zalogowany/a do PBN. <a href="{}" '
                            "onclick=\"this.href='{}?next=' + encodeURIComponent("
                            "window.location.pathname + window.location.search + "
                            'window.location.hash)">Kliknij tutaj, aby '
                            "autoryzować się w PBN</a>. ",
                            cnt,
                            authorize_url,
                            authorize_url,
                        ),
                    )
                else:
                    messages.info(
                        request,
                        f"W kolejce na wysłanie do PBN czeka {cnt} wyedytowanych przez Ciebie rekord(y/ów), ale "
                        f"{pbn_user.username}, z którego konta wysyłasz do PBNu, nie jesteś zalogowany/a do PBN. "
                        f"Przypomij temu użytkownikowy, aby dokonał autoryzacji. ",
                    )

    return {}
