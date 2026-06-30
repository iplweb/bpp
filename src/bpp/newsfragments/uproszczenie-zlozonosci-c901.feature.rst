Uproszczono dziewięć złożonych funkcji oznaczonych dotąd ``# noqa: C901``
(eksport XLSX możliwości odpinania, analiza duplikatów autorów, scalanie
danych CrossRef/PBN, porównywanie metryk autorów oraz cztery eksportery
BibTeX). Powtarzalne łańcuchy ``if``/``elif`` i zduplikowane bloki zastąpiono
tabelami danych (deskryptory kolumn, reguły scoringu, specyfikacje pól) oraz
wydzielonymi funkcjami pomocniczymi. Zachowanie jest niezmienione —
zabezpieczone nowymi testami charakteryzującymi — a kod jest znacznie
czytelniejszy i łatwiejszy w utrzymaniu.
