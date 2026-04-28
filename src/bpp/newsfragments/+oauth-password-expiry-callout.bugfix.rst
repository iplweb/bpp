Naprawiono komunikat o przeterminowanym haśle, który pojawiał się
użytkownikom zalogowanym przez Microsoft (``microsoft_auth``) lub
ORCID (``orcid_integration``) bez formularza zmiany hasła. Hasłem
takich kont zarządza zewnętrzny IdP, więc polityka wygasania nie
powinna ich w ogóle obejmować — middleware
``ConditionalPasswordChangeMiddleware`` już to respektował, ale
context processor ``password_status`` z ``django-password-policies``
nadal sprawdzał wiek hasła w bazie i ustawiał
``password_change_required = True`` w kontekście szablonu, przez co
``base.html`` renderował callout bez formularza (zmienna ``form``
istnieje tylko w widoku zmiany hasła, do którego middleware słusznie
nie przekierowywał). Dodano
``django_bpp.context_processors.conditional_password_status``,
który symetrycznie pomija sprawdzenie dla backendów OAuth z
``EXTERNAL_AUTH_BACKENDS`` i deleguje do oryginalnego context
processora wyłącznie dla zwykłego logowania ``ModelBackend``.
