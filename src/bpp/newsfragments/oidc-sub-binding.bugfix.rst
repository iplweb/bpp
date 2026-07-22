Naprawiono przejęcie konta przez logowanie OIDC: tożsamość jest teraz
trwale wiązana z parą ``(issuer, sub)`` zamiast dopasowywana po adresie
e-mail. Istniejące konta łączy się z SSO świadomie (re-auth hasłem w
profilu), a ``email_verified`` jest wymagane przy zakładaniu konta.
