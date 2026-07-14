Naprawiono błąd, przez który pobranie z PBN pracy nieistniejącej po stronie
PBN (odpowiedź HTTP 422) kończyło się ``TypeError`` zamiast poprawnego
rozpoznania braku pracy. Obsłużono też przypadek, gdy treść odpowiedzi PBN
przychodzi jako bajty.
