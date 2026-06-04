# Eksportowanie do DSpace

Rekordy publikacji można wysyłać do repozytorium
[DSpace](https://dspace.org/) uczelni — wraz z metadanymi i jawnymi
plikami (pełnymi tekstami). Ten rozdział opisuje codzienną wysyłkę
rekordów przez redaktora.

!!! note "Najpierw konfiguracja"
    Eksport działa dopiero, gdy administrator skonfiguruje połączenie
    z DSpace i mapowania kolekcji — patrz
    [Integracja z DSpace](../administrator/integracja-dspace.md). Jeśli
    wysyłka jest pomijana „z powodu braku konfiguracji", zgłoś się do
    administratora.

## Jak wysłać rekordy

1. Wejdź na listę rekordów w **Redagowaniu**: Wydawnictwa ciągłe,
   Wydawnictwa zwarte, Patenty, Prace doktorskie lub Prace
   habilitacyjne.
2. Zaznacz rekordy do wysłania (checkboxy po lewej).
3. Z listy akcji **na dole listy** (pasek akcji jest pod tabelą) wybierz:
   - **Wyślij do DSpace** — wysyłka od razu, z podsumowaniem na ekranie.
     Limit **10 rekordów** naraz.
   - **Wyślij do DSpace w tle** — wysyłka w tle (kolejka zadań), gdy
     rekordów jest dużo. Limit **2000 rekordów** naraz.
4. Zatwierdź akcję.

## Co się dzieje przy wysyłce

- Rekord trafia do uczelni, do których jest **afiliowany** (przez
  jednostki autorów) i które mają skonfigurowany DSpace. Jeden rekord
  może pójść do kilku repozytoriów naraz.
- W obrębie uczelni rekord ląduje w kolekcji dobranej po **charakterze
  formalnym** (zgodnie z mapowaniem ustawionym przez administratora).
- **Jawne** pliki rekordu (tryb dostępu „jawny") są dołączane jako
  załączniki. Przy braku plików powstaje sam rekord metadanowy.
- Ponowna wysyłka **aktualizuje** istniejący rekord w DSpace (a nie
  tworzy duplikatu) i uzgadnia załączniki (dogrywa nowe, usuwa skasowane).

## Statusy w podsumowaniu

Po wysyłce synchronicznej zobaczysz podsumowanie per uczelnia:

| Status | Znaczenie |
|---|---|
| **wyslano** | Utworzono nowy rekord w DSpace. |
| **zaktualizowano** | Zaktualizowano istniejący rekord. |
| **bez_zmian** | Dane i pliki identyczne jak ostatnio — nic nie wysłano. |
| **pominieto** | Wysyłka pominięta; obok podany powód (np. brak mapowania dla charakteru, uczelnia bez aktywnego DSpace). |
| **blad** | Wystąpił błąd; szczegóły zapisane przy rekordzie. |

## Link „zobacz w repozytorium"

Gdy rekord został pomyślnie wysłany, pojawia się link do jego strony
w repozytorium:

- na stronie edycji rekordu — sekcja **„Repozytorium DSpace"**,
- na **publicznej** stronie szczegółów rekordu — w karcie „Linki
  zewnętrzne" jako **„Repozytorium DSpace"** (widoczny dla wszystkich
  odwiedzających),
- w dzienniku **DSpace API → Informacje o wysłaniu do DSpace** (dostęp
  administracyjny).
