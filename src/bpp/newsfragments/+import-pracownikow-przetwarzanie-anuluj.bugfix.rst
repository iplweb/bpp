Na ekranie „Import pracowników — przetwarzanie” przyciski „Anuluj” i „Ponów”
działają ponownie i wyglądają jak przyciski. Wcześniej kliknięcie „Anuluj”
kończyło się cichym błędem 403 (brak tokenu CSRF), ponieważ token nie był
przekazywany w żądaniu htmx przy włączonym ``CSRF_COOKIE_HTTPONLY``; teraz
token jedzie nagłówkiem ``X-CSRFToken``. Dołożono też brakujące style
przycisków sterujących oraz listy etapów operacji.
