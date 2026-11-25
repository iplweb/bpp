# Przemapowanie źródeł (przeniesienie publikacji do innego źródła)

Przemapowanie przenosi hurtem **wszystkie** publikacje z jednego źródła
(czasopisma) do drugiego — na przykład gdy to samo czasopismo jest
w bazie dwa razy albo gdy czasopismo zostało skasowane w PBN i trzeba
przepiąć prace na jego aktualny odpowiednik.

## Gdzie to jest {#gdzie}

| Sytuacja | Gdzie | Przycisk |
|---|---|---|
| zwykłe przemapowanie (np. zdublowane źródło) | strona źródła w części publicznej | **„Przemapuj prace”**, potem **„Przemapuj publikacje”** |
| źródło skasowane w PBN | menu **PBN → źródła skasowane w PBN** | **„Przemapuj”**, potem **„Potwierdź i wykonaj przemapowanie”** |

Na liście źródeł skasowanych w PBN źródło bez żadnych publikacji można
od razu usunąć przyciskiem **„Usuń”**.

Obie funkcje wymagają konta w grupie **„wprowadzanie danych”**
(zob. [Grupy uprawnień](../administrator/grupy-uprawnien.md)).

## Ślad w historii publikacji {#historia}

Każda przemapowana publikacja dostaje wpis na stronie **„Historia”**
w module redagowania: kto i kiedy zmienił źródło, z jakiego na jakie,
oraz numer operacji przemapowania. Przykłady:

- „Przemapowano źródło „Stara nazwa” → „Nowa nazwa” (przemapowanie
  źródeł nr 12).”
- „Przemapowano źródło skasowane w PBN „Stara nazwa” (UID …) → „Nowa
  nazwa” (przemapowanie źródeł PBN nr 7).” — z identyfikatorem (UID)
  skasowanego czasopisma w PBN,
- „Cofnięto przemapowanie źródeł nr 12: …” — po cofnięciu.

Z „Historii” publikacji można też przywrócić jej wersję sprzed
przemapowania. Usunięcie źródła skasowanego w PBN zostawia wpis
„usunięto” w historii tego źródła, a źródło utworzone przy przemapowaniu
z czasopisma PBN — wpis „dodano”.

## Log przemapowań {#log}

Każda operacja jest zapisana w module redagowania na liście
**„Przemapowania źródeł”** (osobna lista dla zwykłych przemapowań
i osobna dla źródeł skasowanych w PBN). Po otwarciu operacji widać:

- kto i kiedy ją wykonał, źródło wyjściowe i docelowe, liczbę publikacji,
- pole **„Przemapowane publikacje”** (dla źródeł PBN: **„Przemapowane
  rekordy”**) — listę objętych publikacji; przy każdej linki
  **„edytuj”** i **„historia”**,
- link **„Pokaż w module redagowania”** — otwiera listę wydawnictw
  ciągłych zawężoną do publikacji z tej operacji (dla operacji do 500
  publikacji).

Publikacja skasowana już po przemapowaniu zostaje na liście z dopiskiem
„rekord usunięty”, bez linków.

## Cofanie {#cofanie}

Zwykłe przemapowanie można cofnąć: na liście **„Przemapowania źródeł”**
w kolumnie „Akcje” jest przycisk **„Cofnij”**. Wracają tylko te
publikacje, które nadal są przy źródle docelowym; cofnięcie również
trafia do historii każdej z nich. Przemapowania źródeł skasowanych w PBN
nie mają przycisku cofania.
