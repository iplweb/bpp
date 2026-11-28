"""Dane demonstracyjne z kreatora pierwszego uruchomienia.

Kreator uruchamia ten sam generator co ``manage.py create_demo_data``
(``bpp.demo_data.orchestrator.run_create``), ale:

* tylko na PUSTEJ bazie (brak uczelni, autorów i publikacji) i tylko przed
  zakończeniem kreatora — to zastępuje podwójne potwierdzenie
  (``--yes-i-am-sure`` + ``--confirm-db``), które w konsoli chroni bazę
  produkcyjną. Warunek sprawdza i widok (pod blokadą wiersza, patrz
  ``rozpocznij_generowanie``), i worker tuż przed generowaniem;
* w tle — jako operacja liveops (worker Celery), bo generowanie trwa kilka
  minut; postęp ląduje w polach operacji, a strona kreatora go odpytuje;
* w skali instalatorów bpp-wsl/bpp-vm (200 autorów, 1000 + 500 prac),
  z prefiksem „Demo — ” w nazwach i z opisami bibliograficznymi
  (``denorm_flush``) na końcu;
* po błędzie próbuje usunąć częściowo wygenerowane dane (manifest), żeby
  kreator mógł wrócić do pytania o dane demo.
"""

from __future__ import annotations

import io
import logging
import tempfile
import time
from datetime import timedelta
from pathlib import Path

from django.core.management import call_command
from django.db import connection, transaction
from django.utils import timezone

from bpp.demo_data.themes.registry import THEMES
from bpp_setup_wizard.models import GenerowanieDanychDemo, KreatorDanychDemo

logger = logging.getLogger(__name__)

# Krótki opis każdego motywu ``create_demo_data --motyw`` dla ekranu wyboru.
# Test pilnuje, żeby każdy motyw z rejestru miał tu opis.
OPISY_MOTYWOW: dict[str, str] = {
    "realistyczny": (
        "Polska uczelnia z realistycznymi nazwiskami, czasopismami "
        "i tytułami prac. Najlepszy do pokazów i szkoleń."
    ),
    "lem": (
        "Świat Stanisława Lema — Ijon Tichy, Solaris, cybernetyka i podróże gwiezdne."
    ),
    "wiedzmin": (
        "Saga o wiedźminie Andrzeja Sapkowskiego — Kaer Morhen, Oxenfurt, "
        "czarodziejki i potwory."
    ),
    "harry-potter": (
        "Uniwersum Harry'ego Pottera — Hogwart, eliksiry, zaklęcia "
        "i magiczne stworzenia."
    ),
    "disney": "Klasyczne postacie Disneya — bajkowe uczelnie, bohaterowie i tytuły.",
    "mitologia": (
        "Bogowie, herosi i stwory mitologii greckiej, rzymskiej, "
        "słowiańskiej i nordyckiej."
    ),
    "trylogia": (
        "Trylogia Henryka Sienkiewicza — Ogniem i mieczem, Potop, Pan Wołodyjowski."
    ),
    "miks": (
        "Wszystkie motywy fabularne naraz — największa różnorodność nazw i tytułów."
    ),
}

MOTYW_DOMYSLNY = "realistyczny"

# Skala jak w instalatorach bpp-wsl / bpp-vm (``bpp-ctl demo``: 200 autorów,
# 1000 + 500 prac) — kilka minut generowania. Pozostałe parametry =
# domyślne ``create_demo_data``.
PARAMETRY_GENERATORA: dict[str, int] = {
    "wydzialow": 10,
    "jednostek_na_wydzial": 5,
    "autorow": 200,
    "ile_ciaglych": 1000,
    "ile_zwartych": 500,
    "od_roku": 2020,
    "do_roku": 2026,
    "procent_z_dyscyplina": 80,
    "procent_z_subdyscyplina": 20,
    "procent_zmiana_dyscypliny": 10,
    "zrodel": 50,
    "wydawcow": 20,
    "batch_size": 500,
}

# Brak zmiany postępu przez tyle czasu = prawdopodobnie zatrzymany worker.
PROG_ZAWIESZENIA = timedelta(minutes=30)


class GenerowanieNiedozwolone(Exception):
    """Generowanie danych demo nie może wystartować (baza nie jest pusta,
    kreator zakończony)."""


class BladGenerowaniaDanychDemo(Exception):
    """Generator danych demo zakończył się błędem."""


def motywy() -> list[tuple[str, str, str]]:
    """(klucz, nazwa, opis) dla wszystkich motywów ``create_demo_data``,
    w kolejności jak ``--motyw`` (``sorted(THEMES)``), domyślny na początku."""
    klucze = sorted(THEMES)
    klucze.remove(MOTYW_DOMYSLNY)
    klucze.insert(0, MOTYW_DOMYSLNY)
    return [(k, THEMES[k].label, OPISY_MOTYWOW.get(k, "")) for k in klucze]


def baza_pusta() -> bool:
    """Czy w bazie nie ma jeszcze danych bibliograficznych.

    Słowniki (języki, typy, dyscypliny) i konta nie przeszkadzają — są na
    każdej świeżej instalacji.
    """
    from bpp.models import Autor, Uczelnia, Wydawnictwo_Ciagle, Wydawnictwo_Zwarte

    return not any(
        model.objects.exists()
        for model in (Uczelnia, Autor, Wydawnictwo_Ciagle, Wydawnictwo_Zwarte)
    )


def ostatnie_generowanie() -> GenerowanieDanychDemo | None:
    return GenerowanieDanychDemo.objects.order_by("-created_on").first()


def rozpocznij_generowanie(user, motyw: str) -> GenerowanieDanychDemo:
    """Utwórz operację generowania i zakolejkuj ją po commicie.

    Idempotentne wobec podwójnego kliknięcia, przeładowania i dwóch kart:
    pod blokadą wiersza ``KreatorDanychDemo`` sprawdzamy, czy generowanie
    już trwa — jeśli tak, zwracamy trwającą operację zamiast nowej.

    :raises GenerowanieNiedozwolone: kreator zakończony albo baza niepusta.
    """
    from first_run_wizard.models import FirstRunWizardState

    if motyw not in THEMES:
        raise GenerowanieNiedozwolone(f"Nieznany motyw danych demo: {motyw!r}.")

    with transaction.atomic():
        KreatorDanychDemo.zablokuj()
        ostatnie = ostatnie_generowanie()
        if ostatnie is not None and ostatnie.w_toku:
            return ostatnie
        if FirstRunWizardState.is_completed():
            raise GenerowanieNiedozwolone(
                "Kreator pierwszego uruchomienia został już zakończony."
            )
        if not baza_pusta():
            raise GenerowanieNiedozwolone(
                "W bazie są już dane (uczelnia, autorzy albo publikacje). "
                "Dane demo można wygenerować tylko na pustej bazie."
            )
        operacja = GenerowanieDanychDemo.objects.create(
            owner=user,
            motyw=motyw,
            status_text="Oczekiwanie na uruchomienie…",
        )
        transaction.on_commit(operacja.enqueue)
    return operacja


# --------------------------------------------------------------------------
# Postęp
# --------------------------------------------------------------------------

# Etapy generatora rozpoznawane po początku opisu paska (``desc`` w
# ``make_progress``), w kolejności wykonywania: (prefiksy, etykieta, waga).
# Wagi z grubsza odpowiadają czasowi etapu w skali kreatora.
ETAPY_GENERATORA: list[tuple[tuple[str, ...], str, int]] = [
    (("Wydziały", "Jednostki"), "Struktura uczelni", 2),
    (("Autor",), "Autorzy", 6),
    (
        ("Źródła", "Wydawcy", "Punktacja", "Dyscypliny źródeł", "Poziomy"),
        "Czasopisma i wydawcy",
        6,
    ),
    (("Wydawnictwa ciągłe", "WC "), "Artykuły w czasopismach", 18),
    (("WZ ",), "Książki i rozdziały", 14),
    (("Streszczenia", "Zgłoszenia"), "Streszczenia i zgłoszenia publikacji", 6),
    (
        (
            "Prace",
            "Patenty",
            "Konferencje",
            "Serie",
            "Granty",
            "Organy",
            "Nagrody",
            "Dwudyscyplinowcy",
            "Brudy",
        ),
        "Rzadsze typy rekordów",
        6,
    ),
    (("Punkty/sloty",), "Przeliczanie punktów i slotów", 22),
    (("PBN",), "Dane PBN", 8),
]
_SUMA_WAG = sum(waga for _, _, waga in ETAPY_GENERATORA)

# Przedziały paska postępu (w procentach) dla kroków generowania.
PROCENT_SLOWNIKI = 1
PROCENT_GENERATOR_OD = 3
PROCENT_GENERATOR_DO = 85
PROCENT_OPISY = 86


class RaportPostepu:
    """Zapisuje postęp do operacji (dla strony kreatora) i wysyła go przez
    liveops (``p``). Zapis do bazy najwyżej raz na ``MIN_ODSTEP`` sekund,
    chyba że zaczyna się nowy krok."""

    MIN_ODSTEP = 1.0

    def __init__(self, operacja: GenerowanieDanychDemo, p) -> None:
        self.operacja = operacja
        self.p = p
        self.procent = 0
        self.tekst = ""
        self._ostatni_zapis = 0.0
        self._etap = -1

    def ustaw(self, procent: float, tekst: str, *, wymus: bool = False) -> None:
        # Pasek nigdy się nie cofa (etapy o nieznanym opisie, zaokrąglenia).
        self.procent = max(self.procent, min(100, int(procent)))
        self.tekst = tekst
        teraz = time.monotonic()
        if not wymus and teraz - self._ostatni_zapis < self.MIN_ODSTEP:
            return
        self._ostatni_zapis = teraz
        GenerowanieDanychDemo.objects.filter(pk=self.operacja.pk).update(
            percent=self.procent,
            status_text=self.tekst[:255],
            postep_zaktualizowano=timezone.now(),
        )
        self.p.status(self.tekst)
        self.p.percent(self.procent)

    def pasek(self, desc: str, n: int, total: int | None) -> None:
        """Obserwator ``bpp.demo_data.progress.obserwuj_postep``."""
        idx = next(
            (
                i
                for i, (prefiksy, _, _) in enumerate(ETAPY_GENERATORA)
                if desc.startswith(prefiksy)
            ),
            None,
        )
        nowy_etap = idx is not None and idx > self._etap
        if nowy_etap:
            self._etap = idx
        if idx is None or idx < self._etap:
            # Pasek spoza tabeli albo z wcześniejszego etapu — tylko opis.
            self.ustaw(self.procent, desc)
            return

        _, etykieta, waga = ETAPY_GENERATORA[idx]
        przed = sum(w for _, _, w in ETAPY_GENERATORA[:idx])
        ulamek = n / total if total else 0
        zakres = PROCENT_GENERATOR_DO - PROCENT_GENERATOR_OD
        procent = PROCENT_GENERATOR_OD + zakres * (przed + waga * ulamek) / _SUMA_WAG
        tekst = f"{etykieta} — {desc}"
        if total and total > 1:
            tekst += f" ({n}/{total})"
        self.ustaw(procent, tekst, wymus=nowy_etap)


class WyjscieGeneratora(io.TextIOBase):
    """``stdout`` dla generatora: zbiera tekst (do komunikatu błędu)
    i przekazuje pełne linie do logu workera."""

    def __init__(self) -> None:
        super().__init__()
        self._bufor: list[str] = []
        self._linia = ""

    def write(self, s: str) -> int:
        self._bufor.append(s)
        self._linia += s
        *pelne, self._linia = self._linia.split("\n")
        for linia in pelne:
            if linia.strip():
                logger.info("dane demo: %s", linia)
        return len(s)

    def ostatnie_linie(self, ile: int = 10) -> str:
        linie = [li for li in "".join(self._bufor).splitlines() if li.strip()]
        return "\n".join(linie[-ile:])


# --------------------------------------------------------------------------
# Generowanie (worker)
# --------------------------------------------------------------------------


def generuj_dane_demo(operacja: GenerowanieDanychDemo, p) -> None:
    """Treść ``GenerowanieDanychDemo.run`` — wykonywana przez worker."""
    from bpp.demo_data.default_dyscypliny import seed_default_dyscypliny
    from bpp.demo_data.preflight import check_required
    from bpp.demo_data.progress import obserwuj_postep

    przejeta = GenerowanieDanychDemo.objects.filter(
        pk=operacja.pk, przejete=False
    ).update(przejete=True)
    if not przejeta:
        raise BladGenerowaniaDanychDemo(
            "To generowanie danych demo zostało już uruchomione — pomijam "
            "powtórzone zadanie."
        )
    if not baza_pusta():
        raise BladGenerowaniaDanychDemo(
            "W bazie są już dane — danych demo nie generuję (dozwolone tylko "
            "na pustej bazie)."
        )

    manifest = Path(tempfile.gettempdir()) / f"bpp_dane_demo_{operacja.pk}.json"
    operacja.manifest = str(manifest)
    operacja.save(update_fields=["manifest"])

    raport = RaportPostepu(operacja, p)
    wyjscie = WyjscieGeneratora()
    try:
        raport.ustaw(PROCENT_SLOWNIKI, "Słownik dyscyplin naukowych", wymus=True)
        seed_default_dyscypliny(stdout=wyjscie)
        brakujace = check_required()
        if brakujace:
            raise BladGenerowaniaDanychDemo(
                "Brakuje słowników wymaganych przez generator: "
                + ", ".join(label for label, _ in brakujace)
            )

        raport.ustaw(PROCENT_GENERATOR_OD, "Uczelnia i struktura", wymus=True)
        with obserwuj_postep(raport.pasek):
            _uruchom_generator(operacja, manifest, wyjscie)

        raport.ustaw(
            PROCENT_OPISY,
            "Opisy bibliograficzne — to może potrwać kilka minut",
            wymus=True,
        )
        call_command("denorm_flush", stdout=wyjscie, stderr=wyjscie)
    except Exception:
        logger.exception(
            "Generowanie danych demo %s nie powiodło się; ostatnie komunikaty:\n%s",
            operacja.pk,
            wyjscie.ostatnie_linie(),
        )
        _usun_czesciowe_dane(operacja, manifest, wyjscie)
        raise

    raport.ustaw(100, "Dane demo gotowe", wymus=True)


def _uruchom_generator(
    operacja: GenerowanieDanychDemo, manifest: Path, wyjscie: WyjscieGeneratora
) -> None:
    from bpp.demo_data.orchestrator import CreateOptions, run_create

    nazwa_bazy = connection.settings_dict["NAME"]
    opts = CreateOptions(
        **PARAMETRY_GENERATORA,
        seed=None,
        manifest_out=manifest,
        # Pusta baza sprawdzona pod blokadą w widoku i ponownie w workerze —
        # odpowiednik ``--yes-i-am-sure --confirm-db <baza>`` z konsoli.
        yes_i_am_sure=True,
        confirm_db=nazwa_bazy,
        motyw=operacja.motyw,
        disable_progress=True,
        uzytkownik=operacja.owner.username,
    )
    try:
        run_create(opts, stdin=io.StringIO(), stdout=wyjscie)
    except SystemExit as e:
        # Preflight / potwierdzenie w run_create kończą komendę przez
        # SystemExit — w workerze zamieniamy to na zwykły błąd operacji.
        raise BladGenerowaniaDanychDemo(
            "Generator danych demo przerwał pracę:\n" + wyjscie.ostatnie_linie()
        ) from e


def _usun_czesciowe_dane(
    operacja: GenerowanieDanychDemo, manifest: Path, wyjscie: WyjscieGeneratora
) -> None:
    """Po błędzie: usuń to, co generator zdążył zapisać (wg manifestu)."""
    from bpp.demo_data.orchestrator import CleanupOptions, run_cleanup

    if manifest.exists():
        try:
            run_cleanup(
                CleanupOptions(
                    manifest=manifest,
                    yes_i_am_sure=True,
                    confirm_db=connection.settings_dict["NAME"],
                    disable_progress=True,
                ),
                stdin=io.StringIO(),
                stdout=wyjscie,
            )
        except (Exception, SystemExit):
            # Sprzątanie jest „najlepszym wysiłkiem” — pierwotny błąd
            # generowania i tak leci dalej; stan bazy opisuje dane_usuniete.
            logger.exception(
                "Nie udało się usunąć częściowych danych demo (manifest %s)",
                manifest,
            )
    operacja.dane_usuniete = baza_pusta()
    operacja.save(update_fields=["dane_usuniete"])
