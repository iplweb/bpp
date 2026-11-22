# Metryki jednostek — zestawienie PDF dla kierownika

**Metryki jednostek** to zestawienie PDF dla kierownika jednostki — kliniki,
katedry, zakładu. Na kilku stronach pokazuje, jak jednostka wypada przed
ewaluacją i co można jeszcze poprawić:

- kto ma **pełne sloty**, a kto ma je **wolne**,
- kto pisze **wyżej punktowane prace** — na tle innych osób w tej samej
  jednostce, a nie całej uczelni,
- **ile punktów** dałoby się jeszcze zdobyć, gdyby wolne sloty wypełnić,
- **jaka część slotów** to prace słabo punktowane,
- **zalecenia** dla każdej grupy osób.

Zestawienie liczy się z [metryk ewaluacyjnych autorów](metryki-ewaluacyjne.md).
Jest tak dobre, jak dane w BPP i ostatnie przeliczenie metryk — patrz
[Zanim zaczniesz](#zanim-zaczniesz).

!!! note "Wersja testowa (beta)"
    Metryki jednostek to nowe zestawienie, oznaczone w BPP znaczkiem
    **„beta”**. Liczby pochodzą z metryk ewaluacyjnych, ale układ, wnioski
    i progi ocen mogą się jeszcze zmienić. Zanim oprzesz na nim decyzje,
    porównaj kluczowe wartości z [metrykami autorów](metryki-ewaluacyjne.md).
    Uwagi zgłaszaj przez pomoc techniczną.

!!! warning "Dane poufne"
    Zestawienie zawiera **imienne oceny pracowników**. Przekazuj je tylko
    osobom, które mają je oglądać, i nadawaj dostęp świadomie — patrz
    [Kto widzi metryki jednostek](#kto-widzi).

## Kto widzi metryki jednostek {#kto-widzi}

| Kto | Które jednostki | Skąd się bierze dostęp |
|---|---|---|
| Superużytkownik, osoba w grupie **„wprowadzanie danych”** | wszystkie | z [grupy uprawnień](../administrator/grupy-uprawnien.md) |
| **Kierownik jednostki** | swoją jednostkę i jej podjednostki | automatycznie — patrz [niżej](#kierownik) |
| Każdy inny zalogowany użytkownik | jednostki wskazane przez administratora, z podjednostkami | pole w profilu użytkownika — patrz [niżej](#nadanie-dostepu) |
| Niezalogowany | żadne | przekierowanie na stronę logowania |

Osoba bez dostępu do danej jednostki dostaje komunikat o braku uprawnień —
także wtedy, gdy jednostka nie ma metryk (nie da się w ten sposób sprawdzić,
które jednostki je mają).

Dostęp do metryk jednostek **nie daje żadnych innych uprawnień**: nie pozwala
edytować danych, oglądać listy metryk autorów, statystyk ani przeliczać
metryk.

### Kierownik jednostki — dostęp automatyczny {#kierownik}

Kierownik widzi swoją jednostkę bez żadnej dodatkowej konfiguracji, jeśli:

1. jego **konto jest powiązane z autorem** — patrz
   [Mój profil autora](../uzytkownik/moj-profil-autora.md) (powiązanie
   ustawia administrator albo BPP dopasowuje je przy logowaniu),
2. ten autor ma w jednostce przypisanie z **funkcją „kierownik”**
   (panel administracyjny → **Autorzy** → autor → jednostki autora, kolumna
   „Funkcja”),
3. przypisanie **trwa dziś** — data „rozpoczął pracę” jest pusta albo
   w przeszłości, a „zakończył pracę” pusta albo w przyszłości.

Gdy w przypisaniu pojawi się data zakończenia pracy, wgląd znika sam od
następnego dnia. Dlatego **funkcję „kierownik” wpisuj starannie** — błędnie
przypisana daje wgląd w oceny całej jednostki.

### Nadanie dostępu innym osobom {#nadanie-dostepu}

Zastępca kierownika, pełnomocnik ds. ewaluacji wydziału, dziekan — każdej
z tych osób administrator może wskazać jednostki ręcznie:

1. Panel administracyjny → **Użytkownicy** → wybierz konto.
2. Sekcja **„Metryki jednostek”**, pole **„Metryki jednostek — jednostki
   do wglądu”** — wpisz początek nazwy i wybierz jednostki.
3. **Zapisz**.

Wskazanie jednostki nadrzędnej (np. wydziału) daje wgląd we **wszystkie
jej podjednostki**. Żeby odebrać dostęp, usuń jednostkę z pola.

## Gdzie to jest {#gdzie-to-jest}

- **Redaktorzy** (grupa „wprowadzanie danych”): menu **ewaluacja → metryki
  jednostek (PDF)** albo przycisk **„Metryki jednostek (PDF)”** nad tabelą
  [metryk ewaluacyjnych](metryki-ewaluacyjne.md#tabela-metryk).
- **Kierownicy i osoby ze wskazanymi jednostkami**: strona **Mój profil**,
  blok **„Metryki jednostek”** — z listą ich jednostek.

Na liście są tylko jednostki, które **mają metryki w wybranym okresie
ewaluacji** (pasek „Okres ewaluacji” u góry strony). Przy każdej:

- **„PDF”** — pobiera plik,
- **„podgląd”** — otwiera to samo w przeglądarce, bez pobierania.

## Zanim zaczniesz {#zanim-zaczniesz}

Zestawienie nie liczy niczego od zera — bierze gotowe
[metryki ewaluacyjne](metryki-ewaluacyjne.md). Żeby liczby miały sens,
po kolei:

1. **Liczba N i dyscypliny autorów.** Zaimportuj dane z POL-on i przelicz
   liczbę N — [Import danych z POL-on i liczba N](import-polon-liczba-n.md)
   (menu **ewaluacja → liczba N**). Od tego zależy, ile slotów ma każda
   osoba. Wątpliwości — [Liczba N — najczęstsze pytania](liczba-n-faq.md).
2. **Dyscypliny przy autorach w pracach.** Praca liczy się osobie tylko
   w dyscyplinie przypisanej w rekordzie — sprawdź
   [rozbieżności dyscyplin](rozbieznosci-dyscyplin.md), a dla osób z dwiema
   dyscyplinami — [Dwudyscyplinowcy](dwudyscyplinowcy.md).
3. **Punktacja czasopism.** Aktualne listy ministerialne —
   [Import list ministerialnych i punktacji czasopism](import-list-ministerialnych.md).
4. **Optymalizacja (opcjonalnie).** Jeśli uczelnia wybiera prace do slotów
   [optymalizacją ewaluacji](optymalizacja-ewaluacji.md) (menu **ewaluacja →
   optymalizacja ewaluacji**), zrób to przed przeliczeniem metryk —
   odpięcia dyscyplin zmieniają to, co liczy się poszczególnym osobom.
5. **Przelicz metryki** — [Przeliczenie metryk](metryki-ewaluacyjne.md#przeliczenie-metryk).
   Metryki same się nie odświeżają; zestawienie pokazuje stan z ostatniego
   przeliczenia (data jest na pierwszej stronie PDF).
6. **Jednostka główna autorów.** Osoba trafia do zestawienia tej jednostki,
   którą metryki uznają za jej **główną jednostkę w okresie ewaluacji**.
   Jeśli ktoś „brakuje” w swojej klinice, sprawdź jego jednostki
   w [edycji autora](autorzy.md).

## Co jest w zestawieniu {#zawartosc}

**Pierwsza strona** — nazwa jednostki, okres, liczba osób, data. Gdy jednostka
ma kilka dyscyplin, także podsumowanie całej jednostki (wypełnienie slotów,
punkty, potencjał) i **tabela dyscyplin**.

Potem **każda dyscyplina osobno** — średnich punktów za slot z różnych
dyscyplin nie da się porównywać:

- **Podsumowanie** — kółko z wypełnieniem slotów (zielone od 90%, żółte
  50–89%, czerwone poniżej 50%), punkty nazbierane, średnia punktów za slot
  na tle całej uczelni w tej dyscyplinie i **szacowany potencjał**.
- **Najważniejsze wnioski** — kilka zdań wyliczonych z danych, np. „trzy
  osoby dają 60% punktów jednostki” albo „31% slotów to prace poniżej
  70 pkt”.
- **Sloty i punkty — każda osoba** — dwa kółka na osobę: wypełnienie slotów
  i punkty (pełne kółko ma osoba z największą liczbą punktów w jednostce)
  oraz ocena jakości prac: ▲ wysoka, ■ typowa, ▼ niska.
- **Wykres bąbelkowy** „Kto wypełnia sloty, a kto pisze lepsze prace”
  (od 3 osób z pracami) — w prawo pełniejsze sloty, w górę wyżej punktowane
  prace, wielkość bąbla to punkty.
- **Lista efektywności** — osoby od najwyższej średniej punktów za slot,
  z porównaniem do mediany jednostki (100% = typowa osoba w jednostce).
- **Struktura punktacji prac w slotach** — jaka część wypełnionych slotów
  to prace za 200, 140, 100, 70, 40 i mniej punktów.
- **Gdzie leży potencjał** — osoby z największą liczbą wolnych slotów
  i szacunkiem punktów do zdobycia.
- **Zalecenia** — co robić z każdą grupą osób.

Dyscypliny z jedną lub dwiema osobami mają **skrócony układ** (karty osób,
wnioski, struktura punktacji, zalecenia), żeby nie zajmowały osobnych stron.

### Cztery grupy osób {#grupy}

Wykres i lista dzielą osoby z pracami na cztery grupy. Granice to **80%
wypełnienia slotów** i **mediana średniej za slot w tej jednostce**
(w danej dyscyplinie) — dlatego podział jest „zeskalowany do realiów
jednostki”: w jednostce z bardzo dobrymi wynikami poprzeczka jest wyżej.

| Grupa | Co to znaczy | Zalecenie |
|---|---|---|
| **Filar jednostki** | pełne sloty, prace co najmniej na poziomie mediany | utrzymać; naturalni liderzy zespołów i współautorzy-mentorzy |
| **Dobre prace, niewykorzystane sloty** | dobre prace, ale za mało | największy zwrot ze wsparcia: czas na pisanie, projekty, zespoły z filarami |
| **Pełne sloty, słabsze prace** | sloty pełne, ale słabiej punktowanymi pracami | celować w czasopisma wyżej punktowane — lepsza praca wypiera słabszą ze slotu |
| **Wymaga wsparcia** | mało prac i poniżej mediany | rozmowa o planach publikacyjnych, współautorstwo z filarami |

Osobno: **Brak prac w okresie** — osoby bez żadnej pracy zaliczonej do
ewaluacji. Najpierw sprawdź dane (dyscyplina w pracach, afiliacja,
[przypięcie dyscypliny](metryki-ewaluacyjne.md#odpinanie)), dopiero potem
wyciągaj wnioski.

### Jak liczony jest potencjał {#potencjal}

**Potencjał = wolne sloty × mediana średniej za slot w jednostce.** To
szacunek, ile punktów przyniosłoby wypełnienie wolnych slotów pracami na
typowym dla jednostki poziomie — nie prognoza. Osoba z 2 wolnymi slotami
w jednostce z medianą 85 pkt/slot ma potencjał ok. +170 pkt.

## Typowe pytania {#typowe-pytania}

**Kierownik nie widzi bloku „Metryki jednostek” w profilu.**
Sprawdź po kolei: czy konto jest powiązane z autorem, czy ten autor ma
w jednostce funkcję „kierownik” w bieżących datach i czy jednostka ma metryki
w wybranym okresie. Najprościej — wskaż mu jednostkę ręcznie
([Nadanie dostępu](#nadanie-dostepu)).

**W zestawieniu brakuje osoby, która pracuje w jednostce.**
Osoba musi mieć metrykę ewaluacyjną (dyscyplinę w okresie i przeliczone
metryki), a jej główną jednostką w okresie musi być ta jednostka. Sprawdź ją
na liście [metryk ewaluacyjnych](metryki-ewaluacyjne.md#filtry-i-eksport)
filtrem po nazwisku.

**Liczby różnią się od tego, co pokazuje SEDN.**
Metryki to narzędzie do planowania z danych w BPP, nie wynik ewaluacji.
Różnice wynikają zwykle z liczby N, dyscyplin w pracach albo przypięć —
patrz [Liczba N w BPP a SEDN](import-polon-liczba-n.md#liczba-n-a-sedn).

**Czy zestawienie porównuje wyniki z poprzednim okresem?**
Jeszcze nie — pokazuje stan z ostatniego przeliczenia metryk.

## Zobacz też

- [Metryki ewaluacyjne autorów](metryki-ewaluacyjne.md)
- [Import danych z POL-on i liczba N](import-polon-liczba-n.md)
- [Optymalizacja ewaluacji — wybór prac do slotów](optymalizacja-ewaluacji.md)
- [Obliczanie slotów](sloty.md)
- [Gdzie sprawdzić punkty i sloty](../uzytkownik/punkty-i-sloty.md)
- [Grupy uprawnień](../administrator/grupy-uprawnien.md)
