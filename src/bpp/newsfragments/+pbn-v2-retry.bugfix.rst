Dodano exponential backoff (5 prób, max ~30 sekund) przy pobieraniu
``PublikacjaInstytucji_V2`` (UUID publikacji z PBN API v2). Poprzednio
jedna próba kończyła się warningiem "nie jest błędem", co myliło użytkowników
— brak V2 oznacza brak możliwości generowania linków do PBN Interfejs
i wysyłki oświadczeń (wymagany UUID). Teraz system automatycznie ponawia
z rosnącym czasem oczekiwania (2s, 4s, 8s, 16s, 32s).

Jeśli po wszystkich próbach nadal nie ma V2 — wyświetlany jest BŁĄD (czerwony)
z sugestią użycia wysyłki w tle (PBN Export Queue) zamiast interaktywnej.

**Ważne dla deploymentu**: przy interaktywnej wysyłce z admina może być potrzebne
zwiększenie timeoutu nginx/gunicorn dla ścieżek ``/admin/`` do minimum 90-120 sekund
(domyślne 30-60s może być za mało przy 5 próbach z opóźnieniami).
