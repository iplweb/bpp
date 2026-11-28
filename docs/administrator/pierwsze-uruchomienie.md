# Pierwsze uruchomienie

Na nowej instalacji (pusta baza danych) BPP zamiast strony głównej
pokazuje kreator konfiguracji. Dopóki kreator nie zostanie ukończony,
każdy, kto otworzy BPP, trafia do kreatora albo na logowanie
administratora.

## Krok 1 — konto administratora

Utwórz pierwsze konto z pełnymi uprawnieniami (login, e-mail, hasło).
Po zapisaniu kreator od razu loguje na to konto.

## Krok 2 — czy utworzyć dane demo?

Kreator pyta, czy wypełnić bazę **danymi demonstracyjnymi**: przykładową
uczelnią z wydziałami, jednostkami, ok. 200 autorami i 1500 publikacjami
(artykuły, książki, rozdziały, zgłoszenia publikacji, punktacja).

!!! warning "Dane demo są fikcyjne"
    Dane demo służą wyłącznie do testów, szkoleń i pokazów. Nie mieszaj
    ich z prawdziwą bibliografią — na instalacji, która ma prowadzić
    rzeczywistą bibliografię uczelni, odpowiedz „Nie”. Nazwy uczelni,
    jednostek i prac zaczynają się od „Demo — ”.

### „Tak, utwórz dane demo”

1. Wybierz motyw danych:

    | Motyw | Opis |
    |---|---|
    | Realistyczny (polski akademicki) | realistyczne nazwiska, czasopisma i tytuły — najlepszy do pokazów i szkoleń |
    | Stanisław Lem | Ijon Tichy, Solaris, cybernetyka |
    | Wiedźmin | saga Andrzeja Sapkowskiego |
    | Harry Potter | Hogwart, eliksiry, zaklęcia |
    | Disney | klasyczne postacie Disneya |
    | Mitologia | mitologia grecka, rzymska, słowiańska i nordycka |
    | Trylogia Sienkiewicza | Ogniem i mieczem, Potop, Pan Wołodyjowski |
    | Miks wszystkich motywów | wszystkie motywy fabularne naraz |

2. Kliknij **Utwórz dane demo**. Generowanie trwa kilka minut i odbywa się
   w tle (w usłudze przetwarzania w tle — workerze Celery). Kreator
   pokazuje pasek postępu i bieżący etap; stronę można zamknąć i wrócić
   do niej później — generowanie trwa dalej.
3. Po zakończeniu kreator przechodzi do BPP. Uczelnię tworzy generator,
   więc kroki „Dane uczelni” i „Integracja z PBN” są pomijane — dane PBN
   można później wpisać w **Administracja → Uczelnia**.

Dane demo można wygenerować tylko raz i tylko na pustej bazie: drugie
kliknięcie, odświeżenie strony czy druga karta przeglądarki pokazują
postęp tego samego generowania.

Jeśli generowanie przerwie błąd, kreator usuwa częściowo utworzone dane
i wraca do pytania — można spróbować ponownie albo wybrać „Nie”. Gdy
usunięcie się nie uda, kreator pokazuje błąd, polecenie
`cleanup_demo_data` do ręcznego sprzątnięcia oraz przycisk **Przejdź
dalej**. Szczegóły błędu są w panelu administracyjnym (operacje
„generowanie danych demo”) i w logu workera.

Jeśli postęp długo się nie zmienia, sprawdź, czy działa worker Celery —
bez niego generowanie nie wystartuje.

### „Nie, skonfiguruję własną uczelnię”

Kreator prowadzi przez dwa kolejne kroki:

- **Dane uczelni** — nazwa, nazwa w dopełniaczu, skrót i to, czy uczelnia
  używa wydziałów;
- **Integracja z PBN** — nazwa i token aplikacji z PBN (patrz
  [Konfiguracja PBN](konfiguracja-pbn.md)); krok można pominąć i uzupełnić
  dane później.

## Instalacje z danymi demo z konsoli

Jeśli dane demo zostały utworzone wcześniej z konsoli (np. instalator
`bpp-ctl init --demo <motyw>` albo `bpp-ctl demo` w bpp-wsl / bpp-vm,
`manage.py create_demo_data`), kreator nie pyta już o dane demo — po
utworzeniu konta administratora od razu przechodzi do BPP.
