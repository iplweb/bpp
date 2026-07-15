Utwardzenia bezpieczeństwa logowania SSO (OIDC): tożsamość i decyzja
o zaufaniu kotwiczone na podpisanym id_token (``sub``/``iss``/
``email_verified`` autorytatywne, kontrola zgodności ``sub`` z userinfo
wg OIDC Core §5.3.2), walidacja ``aud``/``azp`` tokenu względem
``client_id``, czyszczenie nieaktualnych flag trybu linkowania konta,
pomijanie kont zdezaktywowanych przy dopasowaniu po ``(issuer, sub)``
oraz stały dostęp do „Połącz konto z SSO" w profilu (multi-realm).
