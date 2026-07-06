# Edycja danych rekordów - wydawnictwa zwarte, ciągłe, patenty, itp

## Dodawanie autorów do rekordów

Aby dodać autora do rekordu, podczas dodawania lub edycji nowego rekordu kliknij
"Dodaj kolejne powiązanie autora z wyd. ciągłym / wyd. zwartym / patentem ...".

## Zmiana kolejności autorów

Aby zmienić kolejność autorów, skorzystaj z przycisku przeciągania oraz techniki
"przeciągnij i upuść". Po prostu kliknij i przytrzymaj lewym przyciskiem myszy na
przycisku przeciągania i przeciągnij dane powiązanie autora z rekordem w górę
lub w dół. Przycisk przeciągania wygląda w następujący sposób:

![Przycisk przeciągania](../images/editor/przycisk_przeciagania.png)

Możesz "zwinąć" formularz powiązania autora z rekordem aby zmiana kolejności autorów
była łatwiejsza, co ma szczególne znaczenie na monitorach o niewielkiej rozdzielczości.

Działania te również prezentuje film [Zmiana kolejności autorów](https://www.youtube.com/embed/oruEX3CykH8) .

<iframe width="560" height="315" src="https://www.youtube.com/embed/oruEX3CykH8" frameborder="0" allow="autoplay; encrypted-media" allowfullscreen></iframe>

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
