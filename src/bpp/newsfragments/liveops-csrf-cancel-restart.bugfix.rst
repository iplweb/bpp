Naprawiono przyciski „Anuluj"/„Ponów" na stronach postępu importu punktacji
źródeł oraz deduplikatora źródeł — zwracały błąd 403 (CSRF token missing).
Przy ``CSRF_COOKIE_HTTPONLY=True`` biblioteka liveops nie mogła odczytać
tokenu z ciasteczka; token jest teraz wstrzykiwany nagłówkiem ``X-CSRFToken``
przez wrapper ``hx-headers`` (jak w imporcie pracowników).
