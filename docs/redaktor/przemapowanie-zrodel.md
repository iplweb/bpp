# Przemapowanie źródeł (przeniesienie publikacji do innego źródła)

Przemapowanie przenosi hurtem **wszystkie** publikacje z jednego źródła
(czasopisma) do drugiego — na przykład gdy to samo czasopismo jest
w bazie dwa razy albo gdy czasopismo zostało skasowane w PBN i trzeba
przepiąć prace na jego aktualny odpowiednik.

## Gdzie to jest {#gdzie}

Obie funkcje wymagają konta w grupie **„wprowadzanie danych”** (albo
konta superużytkownika; zob. [Grupy
uprawnień](../administrator/grupy-uprawnien.md)).

### Zwykłe przemapowanie (np. zdublowane źródło) {#zwykle}

1. Otwórz stronę źródła w części publicznej i kliknij **„Przemapuj
   prace”**.
2. Wskaż źródło docelowe i potwierdź przyciskiem **„Przemapuj
   publikacje”**.

### Źródło skasowane w PBN {#pbn}

1. Menu **PBN → źródła skasowane w PBN**: lista źródeł BPP powiązanych
   z czasopismem, które w PBN zostało skasowane. Źródło bez żadnych
   publikacji można od razu usunąć przyciskiem **„Usuń”**; przy
   pozostałych jest przycisk **„Przemapuj”**.
2. Strona **„Przemapowanie źródła”**, sekcja **„Wybierz źródło
   docelowe”**: BPP podpowiada kandydatów w dwóch grupach — **„Źródła
   w BPP”** (już istniejące) i **„Źródła z PBN”** (czasopisma, których
   w BPP jeszcze nie ma; wybrane zostanie utworzone jako nowe źródło).
   Kandydaci są ułożeni od najlepszych dopasowań; **„Zobacz w PBN”**
   otwiera czasopismo w PBN. Kliknij wybrane źródło.
3. **„Podgląd zmian”**: zestawienie „Ze źródła (SKASOWANE)” i „Do źródła
   (AKTYWNE)”, liczba rekordów do przemapowania i przykładowe rekordy.
   Nic jeszcze nie zostało zmienione — **„Anuluj”** wraca do wyboru.
4. **„Potwierdź i wykonaj przemapowanie”** przenosi publikacje i dodaje
   je do kolejki eksportu PBN. Tej operacji nie da się cofnąć przyciskiem.

## Ślad w historii publikacji {#historia}

Każda przemapowana publikacja dostaje wpis na stronie **„Historia”**
w module redagowania: kto i kiedy zmienił źródło, z jakiego na jakie,
oraz numer operacji przemapowania. Przy nazwie każdego źródła jest jego
identyfikator w BPP (ID) — dzięki temu wiadomo, o które źródło chodzi,
także gdy oba nazywają się tak samo (scalanie duplikatów). Przykłady:

- „Przemapowano źródło „Gazeta” (ID 120) → „Gazeta” (ID 45)
  (przemapowanie źródeł nr 12).”
- „Przemapowano źródło skasowane w PBN „Stara nazwa” (ID 120, PBN UID …)
  → „Nowa nazwa” (ID 45) (przemapowanie źródeł PBN nr 7).” —
  z identyfikatorem (UID) skasowanego czasopisma w PBN,
- „Cofnięto przemapowanie źródeł nr 12: „Gazeta” (ID 45) → „Gazeta”
  (ID 120).” — po cofnięciu.

Z „Historii” publikacji można też przywrócić jej wersję sprzed
przemapowania. Usunięcie źródła skasowanego w PBN zostawia wpis
„usunięto” w historii tego źródła, a źródło utworzone przy przemapowaniu
z czasopisma PBN — wpis „dodano”.

## Log przemapowań {#log}

Każda operacja jest zapisana w module redagowania, w menu
**Wprowadzanie danych**:

- **„Przemapowania źródeł”** — zwykłe przemapowania,
- **„Przemapowania źródeł PBN”** — przemapowania i usunięcia źródeł
  skasowanych w PBN.

Logi widzi ta sama grupa, która przemapowuje (**„wprowadzanie danych”**),
oraz superużytkownik. Są **tylko do odczytu**: wpisów nie da się dodać
ani zmienić, a usunąć może je wyłącznie superużytkownik. Po otwarciu
operacji widać:

- kto i kiedy ją wykonał, źródło wyjściowe i docelowe, liczbę publikacji,
- pole **„Przemapowane publikacje”** (dla źródeł PBN: **„Przemapowane
  rekordy”**) — listę objętych publikacji; przy każdej linki
  **„edytuj”** i **„historia”**,
- link **„Pokaż w module redagowania”** — otwiera listę wydawnictw
  ciągłych zawężoną do publikacji z tej operacji (dla operacji do 500
  publikacji; bez publikacji z kosza).

Publikacja przeniesiona później do kosza jest oznaczona **„♻️ w koszu
(można przywrócić)”** i ma linki **„pokaż”** i **„historia”** — ze
strony „Historia” można ją przywrócić z kosza. Publikacja usunięta trwale zostaje na liście
z dopiskiem „rekord usunięty trwale”, bez linków.

## Cofanie {#cofanie}

Zwykłe przemapowanie można cofnąć: na liście **„Przemapowania źródeł”**
w kolumnie „Akcje” jest przycisk **„Cofnij”** (z pytaniem
o potwierdzenie). Wracają tylko te publikacje, które nadal są przy
źródle docelowym; cofnięcie również trafia do historii każdej z nich.
Przemapowania źródeł skasowanych w PBN nie mają przycisku cofania.
