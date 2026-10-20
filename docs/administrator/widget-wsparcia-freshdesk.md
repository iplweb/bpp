# Widget wsparcia Freshdesk

W prawym dolnym rogu stron BPP (frontend i moduł redagowania) wyświetla się
zakładka **„Pomoc"**. Otwiera ona formularz zgłoszenia z systemu Freshdesk
(widget Freshworks). Skrypt widgetu jest pobierany z serwera Freshworks dopiero
po najechaniu na zakładkę lub jej kliknięciu.

BPP używa **dwóch osobnych widgetów** Freshdesk:

| Kto | Widget | Uwierzytelnienie |
|-----|--------|------------------|
| użytkownik **zalogowany** | `DJANGO_BPP_FRESHDESK_WIDGET_ID` | token JWT (jeżeli ustawiono sekret), w przeciwnym razie wstępne wypełnienie imienia i e-maila |
| użytkownik **anonimowy** | `DJANGO_BPP_FRESHDESK_WIDGET_ID_ANON` | brak — ochronę przed spamem (captcha) konfiguruje się w ustawieniach tego widgetu w Freshdesku |

Do każdego zgłoszenia trafia adres strony, z której je wysłano (pole
`cf_adres_url`).

## Zmienne konfiguracyjne

Zmienne ustawia się w pliku `.env` (patrz
[Ustawienia zaawansowane](zaawansowane.md)) lub w środowisku kontenera.

| Zmienna | Domyślnie | Znaczenie |
|---------|-----------|-----------|
| `DJANGO_BPP_FRESHDESK_WIDGET_ID` | `205000000433` | ID widgetu dla użytkowników zalogowanych. Pusta wartość wyłącza widget dla zalogowanych. |
| `DJANGO_BPP_FRESHDESK_WIDGET_ID_ANON` | *(pusta)* | ID widgetu dla użytkowników niezalogowanych. Pusta wartość = anonimowi nie widzą zakładki „Pomoc". |
| `DJANGO_BPP_FRESHDESK_WIDGET_JWT_SECRET` | *(pusta)* | Wspólny sekret do podpisywania tokenów JWT widgetu. Pusta wartość = brak uwierzytelnienia JWT. |

ID widgetu to liczba z kodu osadzenia (embed code), który Freshdesk pokazuje
w ustawieniach widgetu — fragment `'widget_id': 205000000433` lub adres
`.../widgets/205000000433.js`.

Przykład:

```bash
DJANGO_BPP_FRESHDESK_WIDGET_ID=205000000433
DJANGO_BPP_FRESHDESK_WIDGET_ID_ANON=205000000999
DJANGO_BPP_FRESHDESK_WIDGET_JWT_SECRET=wklej-tu-shared-secret-z-freshdeska
```

!!! warning "Sekret JWT jest poufny"
    Kto zna sekret, może podpisać token z dowolnym adresem e-mail i wysyłać
    zgłoszenia w imieniu dowolnej osoby. Trzymaj go wyłącznie w `.env` /
    sekretach deploymentu, nigdy w repozytorium. Sekret nie trafia do HTML-a
    stron — tokeny są generowane po stronie serwera.

## Uwierzytelnianie JWT użytkowników zalogowanych

Gdy ustawiono `DJANGO_BPP_FRESHDESK_WIDGET_JWT_SECRET`, zalogowany użytkownik
jest automatycznie uwierzytelniany w widgecie
([dokumentacja Freshdesk](https://support.freshdesk.com/support/solutions/articles/50000000978)):

1. Po najechaniu na zakładkę „Pomoc" (lub kliknięciu) przeglądarka pobiera token z adresu
   `/freshdesk/widget-token/` (dostępny tylko dla zalogowanych).
2. Token (HS256) zawiera imię i nazwisko, adres e-mail użytkownika BPP oraz
   czas wygaśnięcia (1 godzina; Freshdesk dopuszcza maksymalnie 2 godziny).
3. Przed wygaśnięciem tokenu widget sam prosi o nowy — kolejne zapytanie do
   tego samego adresu.

Sekret znajdziesz w Freshdesku w **Admin → Account → Security → Widget
settings** (w Freshdesk Omni: **Admin → Data and Security → Ticket Security**).

Uwagi:

- Użytkownik BPP **bez adresu e-mail** nie może być uwierzytelniony (Freshdesk
  wymaga e-maila w tokenie) — widget otworzy się bez uwierzytelnienia.
- Po włączeniu JWT można w ustawieniach widgetu dla zalogowanych ograniczyć
  formularz kontaktowy i artykuły bazy wiedzy wyłącznie do zalogowanych
  użytkowników.

## Widget dla użytkowników anonimowych

Anonimowy widget jest osobnym widgetem w Freshdesku (inne ID). Włącz w nim
captchę i ewentualnie ogranicz pola formularza — po stronie BPP nie jest
potrzebna żadna dodatkowa konfiguracja poza `DJANGO_BPP_FRESHDESK_WIDGET_ID_ANON`.
Zakładka dla anonimów pojawia się na stronach publicznych oraz na stronie
logowania do modułu redagowania.
