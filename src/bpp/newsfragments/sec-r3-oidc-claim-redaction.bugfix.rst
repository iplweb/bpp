Logowanie diagnostyczne OIDC (Keycloak) nie zrzuca już domyślnie surowych
wartości claimów. Poziom DEBUG loguje teraz wyłącznie nazwy claimów i
zredagowany kształt wartości (typ, długość, klucze), bez danych osobowych
(adresy e-mail, nazwy grup/ról, identyfikatory). Surowe wartości można
tymczasowo odblokować osobnym opt-inem ``DJANGO_BPP_OIDC_DEBUG_CLAIM_VALUES=1``.
