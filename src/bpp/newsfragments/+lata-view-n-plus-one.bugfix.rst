Zoptymalizowano widok listy lat publikacji (``/lata/``) — zamiast
wykonywać osobne zapytanie ``COUNT`` dla każdego rocznika, widok
pobiera liczby publikacji jednym zapytaniem ``GROUP BY``. Na
uczelniach z szerokim zakresem lat publikacji strona ładuje się
wyraźnie szybciej.
