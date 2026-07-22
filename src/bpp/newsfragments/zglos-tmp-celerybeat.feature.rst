Retencja porzuconych plików tymczasowych kreatora zgłaszania publikacji jest
teraz uruchamiana automatycznie jako cykliczne zadanie Celery beat (co 6 h),
obok pozostałych zadań czyszczących. Rdzeń czyszczenia jest współdzielony z
management-commandą ``wyczysc_zglos_tmp`` (do ręcznych/ops uruchomień). Dzięki
temu retencja jedzie razem z kodem aplikacji — nie wymaga osobnej konfiguracji
crona po stronie wdrożenia.
