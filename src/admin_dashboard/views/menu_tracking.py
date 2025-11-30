"""Menu tracking views for admin dashboard."""

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.template.response import TemplateResponse

# Mapowanie emoji dla pozycji menu
MENU_EMOJI_MAPPING = {
    # Główne menu
    "BPP": "🏛️",
    "Dashboard": "📊",
    "Panel": "📊",
    "WWW": "🌐",
    "PBN API": "📡",
    "Dane systemowe": "⚙️",
    "Struktura": "🏢",
    "Wprowadzanie danych": "✏️",
    "Raporty": "📈",
    "Administracja": "👥",
    "Mój profil": "👤",
    # Submenu - autorzy i jednostki
    "Autorzy": "👨‍🔬",
    "Autorzy - udziały": "👨‍🔬",
    "Źródła": "📚",
    "Serie wydawnicze": "📚",
    "Konferencje": "🎤",
    "Wydawcy": "🏢",
    "Wydawnictwa ciągłe": "📰",
    "Wydawnictwa zwarte": "📖",
    "Prace doktorskie": "🎓",
    "Prace habilitacyjne": "🎓",
    "Patenty": "📜",
    # Struktura
    "Uczelnia": "🏫",
    "Wydział": "🎓",
    "Jednostka": "🏛️",
    "Kierunki studiów": "📚",
    # System
    "Charaktery formalne": "📋",
    "Crossref Mapper": "🔗",
    "Charakter PBN": "📋",
    "Dyscypliny naukowe": "🔬",
    "Formularze - wartości domyślne": "📝",
    "Funkcje w jednostce": "👔",
    "Granty": "💰",
    "Grupy pracownicze": "👥",
    "Grupy": "👥",
    "Języki": "🌍",
    "Użytkownicy": "👤",
    # PBN
    "Instytucje": "🏛️",
    "Naukowcy": "👨‍🔬",
    "Publikacje": "📄",
    "Osoby z instytucji": "👥",
    "Słowniki dyscyplin": "📖",
    "Dyscypliny": "🔬",
    "Kolejka eksportu": "⏳",
    "Przesłane dane": "📤",
    # Zgłoszenia
    "Zgłoszenia publikacji": "📬",
    "Powiązania autorów z dyscyplinami": "🔗",
    "Rozbieżności dyscyplin": "⚠️",
    "Rozbieżności dyscyplin źródeł": "⚠️",
    # Web
    "Serwisy": "🌐",
    "Miniblog": "📝",
    "Favicon": "🎨",
    "Szablony": "📄",
    # Ogólne
    "Formularze wyszukiwania": "🔍",
    "Kolumny w module redagowania": "📋",
}


@staff_member_required
def log_menu_click(request):
    """
    Endpoint POST do logowania kliknięć w menu admin.
    Przyjmuje: menu_label, menu_url
    """

    if request.method != "POST":
        return JsonResponse({"error": "Only POST method allowed"}, status=405)

    menu_label = request.POST.get("menu_label", "").strip()
    menu_url = request.POST.get("menu_url", "").strip()

    if not menu_label or not menu_url:
        return JsonResponse(
            {"error": "menu_label and menu_url are required"}, status=400
        )

    # Zapisz kliknięcie
    from admin_dashboard.models import MenuClick

    MenuClick.objects.create(
        user=request.user, menu_label=menu_label, menu_url=menu_url
    )

    return JsonResponse({"status": "ok"})


@staff_member_required
def menu_clicks_stats(request):
    """
    Endpoint GET do pobierania statystyk kliknięć w menu (top 15).
    Renderuje partial template z danymi.
    """
    from django.db.models import Count

    from admin_dashboard.models import MenuClick

    # Agreguj kliknięcia użytkownika - grupuj po menu_label i licz
    top_clicks = (
        MenuClick.objects.filter(user=request.user)
        .values("menu_label", "menu_url")
        .annotate(count=Count("id"))
        .order_by("-count")[:15]
    )

    # Dodaj emoji do każdego rekordu
    enriched_clicks = []
    for click in top_clicks:
        menu_label = click["menu_label"]
        # Znajdź emoji - jeśli nie ma dokładnego dopasowania, użyj pierwszej litery jako fallback
        emoji = MENU_EMOJI_MAPPING.get(
            menu_label, menu_label[0].upper() if menu_label else "📌"
        )
        enriched_clicks.append(
            {
                "menu_label": menu_label,
                "menu_url": click["menu_url"],
                "count": click["count"],
                "emoji": emoji,
            }
        )

    return TemplateResponse(
        request,
        "admin_dashboard/partials/menu_clicks.html",
        {"top_clicks": enriched_clicks},
    )
