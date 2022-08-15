def validate_file_extension_pdf(value):
    import os

    from django.core.exceptions import ValidationError

    ext = os.path.splitext(value.name)[1]  # [0] returns path+filename
    valid_extensions = [
        ".pdf",
    ]
    if not ext.lower() in valid_extensions:
        raise ValidationError(
            "Nieobsługiwany format pliku. Prosimy o pliki w formacie PDF."
        )
