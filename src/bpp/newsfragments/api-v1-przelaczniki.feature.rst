Konfiguracja REST API ``/api/v1/`` w obiekcie Uczelnia: obok istniejącego
głównego wyłącznika doszły opcja „tylko dla zalogowanych" oraz osobne
przełączniki czterech grup endpointów (dane bibliograficzne, wyszukiwanie,
kafelki do osadzania, narzędzia redaktorskie). Domyślnie wszystko działa tak
jak dotychczas. Wyłączone endpointy zwracają czytelny komunikat zamiast
gołego 404, a widget osadzania odróżnia świadomą decyzję administratora
od nieistniejącego autora.
