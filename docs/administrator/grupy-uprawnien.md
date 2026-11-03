# Grupy uprawnień

Uprawnienia w module redagowania nadaje się, dopisując użytkownika do grup.
BPP tworzy grupy automatycznie (m.in. „wprowadzanie danych”, „indeks autorów”,
„dane systemowe”, „struktura”, „web”, „raporty”, „administracja”) i przy
każdej migracji bazy odtwarza ich listę uprawnień (`odtworz_grupy`). Ręczne
okrojenie uprawnień grupy w panelu nie przetrwa więc aktualizacji —
o dostępie decyduje to, **kto należy do grupy**.

## Grupy uprzywilejowane

Część grup pozwala na więcej niż redagowanie danych: na wstawienie
wykonywalnego HTML/JavaScript, który zobaczą inni użytkownicy, albo na
zmianę konfiguracji całego serwisu. Takie grupy należy traktować tak samo
jak konto administratora (superużytkownika).

| Grupa | Co może | Dlaczego to uprawnienie równoważne administracyjnemu |
|---|---|---|
| „administracja” | Edytować użytkowników i grupy (w tym przynależność do grup), formularze wyszukiwania, kolumny modułu redagowania, obsługujących zgłoszenia. | Może dopisać dowolne konto — także własne — do każdej grupy, w tym do grup uprzywilejowanych z tej tabeli. |
| „web” | Edytować szablony przechowywane w bazie (dbtemplates), artykuły na stronie głównej, witryny (`Site`) i favicony. | Szablony z bazy mają pierwszeństwo przed szablonami z dysku, więc można nadpisać **dowolny** szablon serwisu, także stronę logowania i panel administracyjny. Treść artykułów jest wyświetlana jako surowy HTML. W obu przypadkach można wstrzyknąć JavaScript widoczny dla wszystkich użytkowników, w tym superużytkowników. Zmiana domeny witryny wpływa na rozpoznawanie uczelni po nazwie hosta i na adresy bezwzględne generowane przez system. |
| „dane systemowe” | Edytować słowniki systemowe, w tym ustawienia formularzy (formdefaults) z polami „HTML przed” / „HTML po” (`html_before`, `html_after`). | Pola te są wstawiane do formularzy (m.in. raportów i importów) jako kod szablonu Django, bez filtrowania HTML — można w nich umieścić JavaScript wykonywany u każdego, kto otworzy formularz. |
| „raporty” | Edytować definicje raportów (flexible-reports): szablon raportu, tabele, kolumny, źródła danych. | Szablon raportu jest renderowany jako szablon Django bez filtrowania HTML. Zmiana szablonu istniejącego raportu trafia do wszystkich jego odbiorców — zależnie od ustawień raportu także do niezalogowanych. |

Grupy „wprowadzanie danych”, „indeks autorów” i „struktura” nie są na tej
liście: pola z HTML-em, które redagują (tytuły, streszczenia, „informacje”,
„szczegóły”, „uwagi”, biogram autora, tytuł strony głównej, opisy jednostek,
tekst deklaracji dostępności), są przy zapisie lub wyświetlaniu oczyszczane
z niedozwolonych znaczników. Konfigurację integracji uczelni (PBN, Clarivate,
ORCID, DSpace) wraz z danymi dostępowymi widzi i zmienia wyłącznie
superużytkownik.

## Zalecenia

- **Nadawaj grupy uprzywilejowane tylko zaufanym osobom**, tak samo jak
  konto superużytkownika. Osobom, które mają wyłącznie redagować publikacje,
  wystarczy „wprowadzanie danych”.
- **Uwierzytelnianie wieloskładnikowe (MFA).** BPP nie ma własnego drugiego
  składnika logowania (TOTP, klucze sprzętowe). MFA można uzyskać przez
  zewnętrznego dostawcę tożsamości — logowanie przez Microsoft 365, OIDC
  albo [LDAP/ActiveDirectory](zaawansowane.md#konfiguracja-ldap-activedirectory)
  — jeżeli wymusza je ten dostawca. Logowanie loginem i hasłem BPP pozostaje
  przy tym dostępne, więc dla kont uprzywilejowanych warto korzystać
  wyłącznie z logowania przez dostawcę z MFA i stosować
  [politykę haseł](zaawansowane.md#polityka-haseł).
- **Okresowo przeglądaj członków grup.** W panelu administracyjnym:
  „Użytkownicy” — kolumna z listą grup oraz filtr „grupy” w panelu bocznym
  (pokazuje wszystkich członków wybranej grupy); filtr „status
  superużytkownika” pokazuje konta z pełnymi uprawnieniami.
- **Historia zmian.**
    - Szablony z bazy (dbtemplates) mają historię wersji z porównaniem
      zmian (django-reversion) — przycisk „Historia” na stronie szablonu.
    - Rekord uczelni również ma historię wersji (django-reversion).
    - W instalacji produkcyjnej dziennik django-easy-audit rejestruje
      zmiany rekordów uczelni i jednostek.
    - Dla pozostałych obiektów (artykuły, ustawienia formularzy, raporty,
      użytkownicy i grupy) dostępny jest standardowy dziennik panelu
      administracyjnego (przycisk „Historia”): kto i kiedy zmienił obiekt
      oraz które pola — **bez** poprzedniej treści. Jeżeli potrzebny jest
      pełny ślad zmian, rozważ dopisanie tych modeli do
      `DJANGO_EASY_AUDIT_REGISTERED_CLASSES`.
