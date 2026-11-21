# Edycja danych rekordów - wydawnictwa zwarte, ciągłe, patenty, itp

## Dodawanie autorów do rekordów

Aby dodać autora do rekordu, podczas dodawania lub edycji rekordu kliknij
„Dodaj kolejne(go)(-ną)(-ny) powiązanie autora z wyd. ciągłym” (w wydawnictwie
zwartym — „…z wyd. zwartym”, w patencie — „…z patentem”) pod listą autorów.

W formularzu rekordu można w ten sposób wpisać do 25 autorów. Przy dłuższej
liście autorów skorzystaj z przycisku **Autorzy** u góry formularza rekordu.

## Zmiana kolejności autorów

Kolejność autorów zmienia się techniką „przeciągnij i upuść”:

1. Zwiń powiązania autorów — ikoną ⇑ („zwiń wszystkie”) na pasku
   „Powiązania autorów z rekordem” albo klikając nagłówek pojedynczego
   powiązania. Zwinięta lista mieści się na ekranie, co ma znaczenie
   zwłaszcza na mniejszych monitorach.
2. Chwyć lewym przyciskiem myszy przycisk przeciągania (ikona ⇕ po prawej
   stronie nagłówka powiązania) i przeciągnij powiązanie w górę lub w dół.
3. Zapisz rekord.

![Zwinięta lista autorów rekordu z zaznaczonym przyciskiem przeciągania i odnośnikiem dodawania autora](../images/redaktor/wydawnictwa/01-kolejnosc-autorow.png)

Działania te również prezentuje film [Zmiana kolejności autorów](https://www.youtube.com/embed/oruEX3CykH8) .

<iframe width="560" height="315" src="https://www.youtube.com/embed/oruEX3CykH8" frameborder="0" allow="autoplay; encrypted-media" allowfullscreen></iframe>

## Data albo rok udostępnienia w otwartym dostępie {#data-udostepnienia-oa}

W formularzu artykułu (wydawnictwa ciągłego) oraz książki i rozdziału
(wydawnictwa zwartego), w zwijanej sekcji **OpenAccess**, są dwa pola:

- **OpenAccess: data udostępnienia** — pełna data (dzień, miesiąc, rok),
  w której praca została udostępniona w otwartym dostępie,
- **OpenAccess: rok udostępnienia** — sam rok, gdy dokładna data nie jest
  znana.

Wypełnij **jedno z nich, nie oba** — przy zapisie z wypełnionymi obydwoma
polami formularz pokaże błąd. Rok musi mieścić się w zakresie od 1900 do
bieżącego roku powiększonego o 10 lat.

Przy wysyłce do PBN:

- wpisana data trafia do PBN jako pełna data udostępnienia,
- wpisany sam rok trafia do PBN jako rok udostępnienia — **bez miesiąca**;
  BPP nie dopisuje żadnego miesiąca ani dnia,
- gdy oba pola są puste, BPP użyje daty dostępu do strony WWW
  („Dostęp dnia (wolny dostęp)”, a potem „Dostęp dnia (płatny dostęp)”),
  o ile ją podano; inaczej data udostępnienia nie jest wysyłana.
  Rok wpisany w sekcji OpenAccess ma pierwszeństwo przed tymi datami.

PBN może nie przyjąć samego roku — jego walidacja żąda „pełnej daty albo
miesiąca i roku”. Jeśli przy wysyłce pojawi się taki komunikat, wpisz
w pracy pełną datę udostępnienia (zob.
[czytanie błędów wysyłki](pbn-wysylka-i-synchronizacja.md)).

Prace pobierane z PBN, dla których PBN zna tylko rok udostępnienia, mają
ten rok wpisany w polu **OpenAccess: rok udostępnienia**.

## Dlaczego nie można usunąć pracy z wpisanym „Odpowiednikiem w PBN"

Przy próbie skasowania wydawnictwa ciągłego lub zwartego może się okazać, że
system nie udostępnia przycisku **Usuń**, a przy próbie usunięcia pojawia się
komunikat **„Brak uprawnień do usuwania"** — nawet jeśli masz uprawnienia
redaktora.

Jest to **działanie celowe, a nie błąd**. Rekordu **nie da się usunąć tak długo,
jak długo ma wypełnione pole „Odpowiednik w PBN"** — czyli dopóki jest powiązany
z konkretną publikacją po stronie PBN. Dotyczy to zarówno wydawnictw ciągłych,
jak i zwartych.

### Dlaczego tak jest

Jeżeli praca została wysłana do PBN, BPP zapamiętuje powiązanie z nią w polu
„Odpowiednik w PBN". Gdyby można było skasować taki rekord wyłącznie w BPP,
praca **nadal pozostałaby w PBN**, a BPP straciłoby jedyną informację o tym, gdzie
w PBN się ona znajduje. Powstałby „osierocony" wpis w PBN, którego z poziomu BPP
nie dałoby się już ani usunąć, ani poprawić. Blokada chroni więc przed
rozjechaniem się danych między BPP a PBN.

### Jak prawidłowo usunąć taką pracę

1. **Najpierw usuń pracę po stronie PBN** — z **profilu Twojej instytucji**
   w PBN (a nie z samego repozytorium). Otwórz ją w PBN korzystając z odnośnika
   przy polu „Odpowiednik w PBN", **zanim** je wyczyścisz. Ten krok wykonujesz
   bezpośrednio w PBN — leży on po stronie redaktora / instytucji.
2. **Wyczyść pole „Odpowiednik w PBN"** w rekordzie w BPP i zapisz rekord. W ten
   sposób zdejmujesz powiązanie z PBN.
3. Po zapisaniu przycisk **Usuń** stanie się ponownie dostępny i będziesz mógł
   skasować rekord w BPP.

!!! warning "Zachowaj kolejność kroków"
    Pole „Odpowiednik w PBN" to jedyny ślad łączący rekord BPP z konkretną
    publikacją w PBN. Jeśli wyczyścisz je, zanim usuniesz pracę z PBN, stracisz
    informację, którą publikację w PBN należy skasować. Dlatego najpierw zajmij
    się PBN, a dopiero potem czyść pole i kasuj rekord w BPP.
