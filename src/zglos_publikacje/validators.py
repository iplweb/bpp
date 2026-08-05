import os

from django.core.exceptions import ValidationError

# Limity uploadu formularza zgłaszania publikacji (finding #2 z review
# bezpieczeństwa: anonimowy DoS przez uploady). Egzekwowane w walidacji
# formularza (dobre UX błędu) oraz defensywnie w warstwie utrwalania.
MAX_ROZMIAR_PLIKU = 20 * 1024 * 1024  # 20 MB / plik
MAX_LICZBA_PLIKOW = 5  # max plików w jednym żądaniu


def validate_file_extension_pdf(value):
    ext = os.path.splitext(value.name)[1]  # [0] returns path+filename
    valid_extensions = [
        ".pdf",
    ]
    if ext.lower() not in valid_extensions:
        raise ValidationError(
            "Nieobsługiwany format pliku. Prosimy o pliki w formacie PDF."
        )


def validate_file_size(value):
    """Odrzuć pojedynczy plik przekraczający MAX_ROZMIAR_PLIKU."""
    if value.size > MAX_ROZMIAR_PLIKU:
        raise ValidationError(
            f"Plik jest za duży (maksymalny rozmiar to "
            f"{MAX_ROZMIAR_PLIKU // (1024 * 1024)} MB)."
        )
