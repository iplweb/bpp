# REST API (`/api/v1/`)

BPP wystawia publiczne REST API pod adresem `/api/v1/`. Domyślnie działa
w całości — ta strona opisuje, jak wyłączyć jego części, gdy z jakiegoś
powodu nie chcesz ich udostępniać.

Ustawienia znajdziesz w panelu administracyjnym: **Uczelnia** → sekcja
**REST API (/api/v1/)**.

Przełączniki dotyczą wyłącznie `/api/v1/`. Nie wpływają na OAI-PMH
(`/oai/`), eksport CERIF (`/cerif-oai/`) ani na działanie samej strony WWW.

## Sześć przełączników

### Włącz REST API (/api/v1/)

Główny wyłącznik. Odznaczenie sprawia, że całe `/api/v1/` odpowiada kodem
404 z informacją, że API zostało wyłączone przez administratora.

**Nie dotyczy kafelków do osadzania** — te mają własny przełącznik
i działają niezależnie. Dzięki temu wyłączenie API nie psuje list
publikacji wklejonych na stronach WWW jednostek.

### REST API tylko dla zalogowanych

Domyślnie **odznaczone**. Po zaznaczeniu niezalogowany klient dostaje kod
401 zamiast danych; zalogowany pracuje normalnie.

Nie dotyczy kafelków do osadzania — te z założenia wiszą na publicznych
stronach i nie mają jak się zalogować.

Użyj tego, gdy chcesz udostępniać dane integracjom (które potrafią się
uwierzytelnić), ale nie chcesz, żeby ktokolwiek mógł anonimowo pobrać
całą bazę.

### Udostępniaj dane bibliograficzne

Słowniki (charaktery formalne, języki, dyscypliny), struktura uczelni,
autorzy, rekordy publikacji, źródła i wydawcy. To główna zawartość API.

### Udostępniaj wyszukiwanie

Endpoint `/api/v1/szukaj/` — pełnotekstowe wyszukiwanie po wszystkich
publikacjach. Jest kosztowny obliczeniowo i objęty osobnym limitem
zapytań; odznacz, jeśli mimo limitu obciąża serwer.

### Udostępniaj kafelki do osadzania

Endpointy `/api/v1/recent_author_publications/`
i `/api/v1/recent_unit_publications/`, z których korzysta widget
`bpp-publikacje.js`.

!!! warning "Odznaczenie zgasi widgety na cudzych stronach"

    Z tych endpointów korzystają listy publikacji wklejone na stronach WWW
    wydziałów, katedr i pracowników — poza Twoją kontrolą. Po odznaczeniu
    listy przestaną się wyświetlać.

    Widget **nie** pokaże ramki z komunikatem o błędzie — strona będzie
    wyglądać normalnie, po prostu bez listy. Powód trafi do komentarza
    HTML widocznego w „pokaż źródło", żeby osoba opiekująca się tamtą
    stroną mogła się zorientować, co się stało.

### Udostępniaj narzędzia redaktorskie

Zapytania DjangoQL (`/api/v1/zapytanie/`) i raport slotów uczelni.

Te endpointy wymagają konta redaktora także wtedy, gdy przełącznik jest
zaznaczony — decyduje on wyłącznie o tym, czy w ogóle istnieją.

## Co widzi klient po wyłączeniu

| Sytuacja | Kod | Komunikat |
|---|---|---|
| Główny wyłącznik odznaczony | 404 | REST API tego serwisu zostało wyłączone przez administratora. |
| Odznaczona grupa | 404 | Ta część REST API została wyłączona przez administratora tego serwisu. |
| „Tylko dla zalogowanych", klient anonimowy | 401 | REST API tego serwisu jest dostępne wyłącznie dla zalogowanych użytkowników. |

Strona `/api/v1/` przy częściowym wyłączeniu pokazuje wyłącznie czynne
grupy — nie reklamuje adresów, które i tak nie odpowiedzą.

Odpowiedzi wynikające z tych przełączników zawierają dodatkowe pole
`powod`. Dzięki niemu program po drugiej stronie odróżnia świadomą decyzję
administratora od zwykłego błędu (na przykład literówki w identyfikatorze
autora), które oba są kodem 404.

## Odzyskanie dostępu

Wszystkie przełączniki są odwracalne i działają natychmiast — zaznacz
z powrotem w panelu administracyjnym, zapisz, gotowe. Nie wymagają
restartu serwera ani przebudowy niczego.
