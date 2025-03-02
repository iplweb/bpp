def check_mongoId(s: str):
    """Sprawdza, czy to prawidłowy mongoId z PBNu"""

    valid_letters = "0123456789abcdef"

    if len(s) == 24 and all(letter in valid_letters for letter in s.lower()):
        try:
            int(s, 16)
        except (TypeError, ValueError):
            return False

        return True

    return False
