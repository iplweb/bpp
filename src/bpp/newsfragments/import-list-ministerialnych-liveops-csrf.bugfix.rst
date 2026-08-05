Import list ministerialnych: przyciski „Anuluj"/„Ponów" na stronie live
dostają teraz token CSRF nagłówkiem ``X-CSRFToken`` (wrapper
``hx-headers`` wokół regionu live-operacji). Bez tego przy
``CSRF_COOKIE_HTTPONLY=True`` POST-y liveops kończyły się błędem 403.
