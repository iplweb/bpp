Bezpieczeństwo: zamknięto obejście proof-of-work CAPTCHA w kreatorze
zgłoszeń publikacji. Bot mógł, ustawiając wprost ``current_step`` formularza
wieloetapowego, przeskoczyć krok z captchą i utrwalić pliki na dysku bez
rozwiązania PoW (wektor disk-exhaustion). Pliki są teraz zapisywane
wyłącznie po realnym zaliczeniu kroku z captchą (serwerowy marker w sesji).
