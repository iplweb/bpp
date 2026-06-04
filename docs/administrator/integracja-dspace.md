# Integracja z DSpace — dla administratora

BPP potrafi wysyłać rekordy publikacji do zewnętrznego repozytorium
[DSpace](https://dspace.org/) (wspierane wersje 7–9) przez REST API.
Każda uczelnia ma **własną** instalację DSpace, własną konfigurację
i własne kolekcje — eksport jest więc konfigurowany per uczelnia.

Ten rozdział opisuje konfigurację po stronie administratora. Codzienną
wysyłkę rekordów przez redaktora opisuje rozdział
[Eksportowanie do DSpace](../uzytkownik/eksportowanie-do-dspace.md).

## Wymagania

- Działająca instalacja DSpace 7–9 z włączonym REST API (adres zwykle
  kończy się na `/server/api`).
- Konto użytkownika DSpace z prawem tworzenia itemów w docelowych
  kolekcjach (login + hasło do API).

## 1. Konfiguracja połączenia na obiekcie Uczelnia

Przejdź do **Redagowanie → Struktura → Uczelnia**, otwórz obiekt uczelni
i rozwiń sekcję **„DSpace"**. Ustaw:

| Pole | Znaczenie |
|---|---|
| **Włącz eksport do DSpace** | Główny przełącznik. Dopóki wyłączony, rekordy tej uczelni nie są wysyłane. |
| **Adres API DSpace** | Pełny adres REST API, np. `https://repozytorium.uczelnia.pl/server/api`. |
| **Użytkownik API DSpace** | Login konta API. |
| **Hasło API DSpace** | Hasło konta API. Przechowywane w bazie **w postaci zaszyfrowanej**. |
| **Domyślny język dc.language.iso** | Język wpisywany do metadanych Dublin Core, gdy rekord go nie określa (domyślnie `pl`). |

!!! note "Bezpieczeństwo hasła"
    Hasło API jest szyfrowane (Fernet) wspólnym kluczem instalacji.

## 2. Mapowania kolekcji (Charakter formalny → kolekcja DSpace)

W obrębie jednej uczelni o tym, do której **kolekcji** DSpace trafi
rekord, decyduje jego **charakter formalny**. Mapowania definiujesz w
**DSpace API → Mapowania DSpace**.

Aby dodać mapowanie (**Dodaj mapowanie DSpace**):

1. **Uczelnia** — gdy w systemie jest tylko jedna uczelnia, jest wybrana
   automatycznie; przy wielu uczelniach podstawiana jest uczelnia
   bieżącego serwisu.
2. **Charakter formalny** — np. „Artykuł", „Monografia".
3. **UUID kolekcji DSpace** — po wybraniu uczelni pole zamienia się w
   **listę kolekcji pobieraną na żywo z DSpace** tej uczelni. Wybierz
   kolekcję z listy zamiast przepisywać UUID ręcznie.

!!! tip "Gdy lista kolekcji się nie pobiera"
    Picker odpytuje DSpace na żywo (z krótkim limitem czasu). Jeśli DSpace
    jest chwilowo nieosiągalny, błędnie skonfigurowany albo zwróci pustą
    listę, pole wraca do zwykłego wpisywania UUID — możesz wtedy wkleić
    identyfikator kolekcji ręcznie. Linkiem **„Wpisz UUID ręcznie"** /
    **„Wybierz kolekcję z listy"** przełączasz się między trybami.

Reguła routingu: para **(Uczelnia, Charakter formalny)** musi być
unikalna. Jeżeli rekord ma charakter, dla którego **nie ma** mapowania
w danej uczelni, rekord **nie zostanie wysłany** do tej uczelni — redaktor
zobaczy w podsumowaniu wysyłki konkretny powód pominięcia.

## 3. Podgląd wysłanych rekordów i link do repozytorium

**DSpace API → Informacje o wysłaniu do DSpace** to dziennik wszystkich
prób eksportu (tylko do odczytu). Dla każdego wpisu widać uczelnię,
status, UUID itemu oraz — gdy rekord udało się wysłać — kolumnę
**„Zobacz w repozytorium"** z bezpośrednim linkiem do rekordu w DSpace.

Link budowany jest z **handle** (trwałego identyfikatora) zwracanego przez
DSpace przy tworzeniu itemu, jako `{adres repozytorium}/handle/{handle}`,
gdzie adres repozytorium wyprowadzany jest z **Adresu API DSpace** (po
odcięciu `/server/api`). Rekordy wysłane zanim wdrożono zapisywanie
handle uzupełnią go automatycznie przy najbliższej ponownej wysyłce.

Ten sam link pojawia się też:

- na stronie edycji rekordu (Wydawnictwa ciągłe/zwarte, Patenty, Prace
  doktorskie/habilitacyjne) — sekcja **„Repozytorium DSpace"**,
- na **publicznej** stronie szczegółów rekordu — w karcie „Linki
  zewnętrzne" jako **„Repozytorium DSpace"**.
