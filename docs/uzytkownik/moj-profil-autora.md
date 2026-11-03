# Mój profil autora — samodzielna edycja strony autora

Każdy autor ma w BPP publiczną
[stronę autora](przegladanie-i-wyszukiwanie.md#strona-autora). Część danych
na niej — **zdjęcie, biogram, linki do profili w innych serwisach** oraz
**wyróżnione publikacje** — autor może uzupełnić **sam**, po zalogowaniu,
bez pośrednictwa redaktora.

## Kto może edytować

Edycja jest dostępna dla zalogowanego użytkownika, którego **konto jest
powiązane z rekordem autora**. Autor edytuje wyłącznie **własną** stronę.

Powiązanie zwykle tworzy się samo: przy wejściu na stronę „Mój profil” system
próbuje dopasować konto do autora — najpierw po adresie e-mail, potem po
imieniu i nazwisku (o ile dopasowanie jest jednoznaczne). Jeśli to się nie
uda, powiązanie ustawia redaktor (patrz
[instrukcja redaktora — powiązanie konta z autorem](../redaktor/autorzy.md#powiązanie-konta-użytkownika-z-autorem)).

## Jak wejść do edycji

1. Zaloguj się do BPP.
2. Na górnej belce rozwiń menu **„wyloguj”** i wybierz **„mój profil”**.
3. Jeśli konto jest powiązane z autorem, zobaczysz ramkę **„Powiązany autor”**
   z odnośnikiem do Twojej strony autora oraz przyciskiem
   **„Edytuj swoją stronę”** — kliknij go.

Strona edycji ma adres `/bpp/profil/edycja/`.

!!! note
    Jeśli zamiast ramki „Powiązany autor” widzisz komunikat, że konto nie
    jest powiązane z autorem — poproś redaktora BPP w swojej uczelni
    o ustawienie powiązania.

## Co można zmienić

### Zdjęcie

Wgraj plik ze zdjęciem (do **5 MB**). System sam kadruje je do kwadratu,
skaluje i zapisuje w formacie WebP. Na stronie autora zdjęcie można kliknąć,
aby je powiększyć.

### Biogram

Krótka nota o sobie, wyświetlana obok zdjęcia na stronie autora.

- **Format** — wybierz **Markdown** (prosty zapis: `**pogrubienie**`,
  `*kursywa*`, listy `-`, nagłówki `###`, linki `[tekst](adres)`) albo
  **HTML**.
- **Podgląd na żywo** — obok pola treści widać od razu, jak biogram będzie
  wyglądał na stronie.

Ze względów bezpieczeństwa z biogramu usuwane są skrypty i niebezpieczne
znaczniki; linki dostają atrybut `nofollow`.

### Profile w innych serwisach

Identyfikatory **Web of Science** (ResearcherID), **Scopus** (Author ID)
i **Google Scholar** oraz **adres profilu w portalu uczelni** (np. PPM).
W polach identyfikatorów można wkleić **cały adres profilu** skopiowany
z przeglądarki — system sam wyciągnie z niego identyfikator i sprawdzi jego
format.

Po wpisaniu zmian kliknij **„Zapisz zmiany”**.

## Wyróżnione publikacje

Pod formularzem edycji jest przycisk **„Zarządzaj wyróżnionymi
publikacjami”** (adres `/bpp/profil/edycja/wybrane-publikacje/`). Można tam:

- wyszukać i **dodać** prace — wyszukiwarka podpowiada **wyłącznie Twoje
  prace**,
- **usuwać** je,
- **zmieniać kolejność** strzałkami.

!!! note
    Wyróżnione publikacje pojawiają się na stronie autora tylko wtedy, gdy
    uczelnia włączyła tę sekcję w układzie strony autora (patrz
    [instrukcja administratora — układ podstrony autora](../administrator/ogolna.md#układ-podstrony-autora-profil-autora)).

## Czego nie zmienisz samodzielnie

Pozostałe dane na stronie autora — m.in. jednostka i historia zatrudnienia,
dyscypliny, stopnie naukowe, ORCID i powiązanie z PBN, a także sama lista
publikacji i ich punktacja — prowadzi **redaktor BPP** w module redagowania.
W razie błędów w tych danych zgłoś je redaktorowi swojej uczelni.
