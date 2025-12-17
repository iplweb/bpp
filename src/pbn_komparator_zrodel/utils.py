import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from tqdm import tqdm

from bpp.models import Dyscyplina_Naukowa, Punktacja_Zrodla, Zrodlo
from import_common.normalization import normalize_kod_dyscypliny
from pbn_downloader_app.freshness import (
    DATA_FRESHNESS_MAX_AGE_DAYS,
    is_pbn_journals_data_fresh,
)

from .models import BrakujacaDyscyplinaPBN, KomparatorZrodelMeta, RozbieznoscZrodlaPBN

logger = logging.getLogger(__name__)

# Re-export for backwards compatibility
__all__ = [
    "is_pbn_journals_data_fresh",
    "DATA_FRESHNESS_MAX_AGE_DAYS",
    "znajdz_brakujace_dyscypliny_pbn",
    "aktualizuj_brakujace_dyscypliny_pbn",
    "get_brakujace_dyscypliny_pbn",
]


def znajdz_brakujace_dyscypliny_pbn():
    """
    Znajduje dyscypliny występujące w danych PBN (pbn_api.Journal),
    które nie istnieją w BPP (Dyscyplina_Naukowa).

    Returns:
        dict: Słownik {kod_pbn: {"kod_bpp": ..., "nazwa": ..., "count": ...}}
              Pusty słownik jeśli wszystkie dyscypliny istnieją.
    """
    from pbn_api.models import Journal

    # Cache dyscyplin BPP
    bpp_kody = set(Dyscyplina_Naukowa.objects.values_list("kod", flat=True))

    brakujace = {}

    for journal in Journal.objects.all():
        disciplines = journal.value("object", "disciplines", return_none=True)
        if not disciplines:
            continue

        for disc in disciplines:
            code = disc.get("code")
            name = disc.get("name", "")
            if not code:
                continue

            kod_bpp = normalize_kod_dyscypliny(str(code))
            if not kod_bpp:
                continue

            if kod_bpp not in bpp_kody:
                if code not in brakujace:
                    brakujace[code] = {"kod_bpp": kod_bpp, "nazwa": name, "count": 0}
                brakujace[code]["count"] += 1

    return brakujace


def aktualizuj_brakujace_dyscypliny_pbn():
    """
    Znajduje i zapisuje brakujące dyscypliny do bazy danych.
    Wywoływana po pobraniu danych źródeł z PBN (w download_journals task).

    Returns:
        int: Liczba znalezionych brakujących dyscyplin.
    """
    from pbn_api.models import Journal

    # Cache dyscyplin BPP
    bpp_kody = set(Dyscyplina_Naukowa.objects.values_list("kod", flat=True))

    brakujace = {}

    for journal in Journal.objects.all():
        disciplines = journal.value("object", "disciplines", return_none=True)
        if not disciplines:
            continue

        for disc in disciplines:
            code = disc.get("code")
            name = disc.get("name", "")
            if not code:
                continue

            kod_bpp = normalize_kod_dyscypliny(str(code))
            if not kod_bpp:
                continue

            if kod_bpp not in bpp_kody:
                if code not in brakujace:
                    brakujace[code] = {"kod_bpp": kod_bpp, "nazwa": name, "count": 0}
                brakujace[code]["count"] += 1

    # Zapisz do bazy (usuń stare, dodaj nowe)
    with transaction.atomic():
        BrakujacaDyscyplinaPBN.objects.all().delete()
        for kod_pbn, info in brakujace.items():
            BrakujacaDyscyplinaPBN.objects.create(
                kod_pbn=str(kod_pbn),
                kod_bpp=info["kod_bpp"],
                nazwa=info["nazwa"],
                liczba_zrodel=info["count"],
            )

    logger.info(f"Zaktualizowano brakujące dyscypliny PBN: {len(brakujace)} pozycji")
    return len(brakujace)


def get_brakujace_dyscypliny_pbn():
    """
    Pobiera zapisane brakujące dyscypliny z bazy danych.

    Returns:
        dict: Słownik {kod_pbn: {"kod_bpp": ..., "nazwa": ..., "count": ...}}
              Pusty słownik jeśli brak danych.
    """
    return {
        bd.kod_pbn: {
            "kod_bpp": bd.kod_bpp,
            "nazwa": bd.nazwa,
            "count": bd.liczba_zrodel,
        }
        for bd in BrakujacaDyscyplinaPBN.objects.all()
    }


def is_discrepancies_list_stale(max_age_days=DATA_FRESHNESS_MAX_AGE_DAYS):
    """
    Sprawdza czy lista rozbieżności jest starsza niż max_age_days.

    Returns:
        tuple: (is_stale: bool, age_days: int or None)
    """
    meta = KomparatorZrodelMeta.get_instance()
    if not meta.ostatnie_uruchomienie:
        return False, None  # Nigdy nie zbudowano - nic do usunięcia

    age = timezone.now() - meta.ostatnie_uruchomienie
    return age > timedelta(days=max_age_days), age.days


def cleanup_stale_discrepancies(max_age_days=DATA_FRESHNESS_MAX_AGE_DAYS):
    """
    Usuwa rozbieżności jeśli są starsze niż max_age_days.

    Returns:
        tuple: (was_cleaned: bool, deleted_count: int)
    """
    is_stale, age_days = is_discrepancies_list_stale(max_age_days)
    if is_stale:
        count = RozbieznoscZrodlaPBN.objects.all().delete()[0]
        meta = KomparatorZrodelMeta.get_instance()
        meta.ostatnie_uruchomienie = None
        meta.statystyki = {}
        meta.save()
        logger.info(
            f"Usunięto {count} przestarzałych rozbieżności (wiek: {age_days} dni)"
        )
        return True, count
    return False, 0


class KomparatorZrodelPBN:
    """
    Klasa porównująca dane źródeł między BPP a PBN.
    Wykorzystuje ThreadPoolExecutor do równoległego przetwarzania.
    """

    def __init__(
        self,
        min_rok=2022,
        clear_existing=False,
        show_progress=True,
        progress_callback=None,
    ):
        self.min_rok = min_rok
        self.clear_existing = clear_existing
        self.show_progress = show_progress
        self.progress_callback = progress_callback

        # Thread-safe stats
        self._stats_lock = threading.Lock()
        self._stats = {
            "processed": 0,
            "points_discrepancies": 0,
            "discipline_discrepancies": 0,
            "skipped_no_pbn": 0,
            "skipped_no_data": 0,
            "errors": 0,
        }
        self._dyscypliny_cache = None

    @property
    def stats(self):
        """Zwraca kopię stats (thread-safe read)."""
        with self._stats_lock:
            return dict(self._stats)

    def _increment_stat(self, key, value=1):
        """Thread-safe increment stat."""
        with self._stats_lock:
            self._stats[key] += value

    def _get_dyscypliny_cache(self):
        """Pobiera cache kodów dyscyplin."""
        if self._dyscypliny_cache is None:
            self._dyscypliny_cache = {
                d.kod: d for d in Dyscyplina_Naukowa.objects.all()
            }
        return self._dyscypliny_cache

    def clear_discrepancies(self):
        """Usuwa wszystkie istniejące rozbieżności."""
        count = RozbieznoscZrodlaPBN.objects.all().delete()[0]
        logger.info(f"Usunięto {count} istniejących rozbieżności")
        return count

    def get_pbn_points_for_year(self, journal, rok: int):
        """Pobiera punkty z PBN dla danego roku."""
        points_data = journal.value("object", "points", return_none=True)
        if not points_data:
            return None
        year_data = points_data.get(str(rok))
        if year_data:
            return year_data.get("points")
        return None

    def get_pbn_disciplines(self, journal):
        """Pobiera listę dyscyplin z PBN (lista słowników z polami code, name, etc.)."""
        return journal.value("object", "disciplines", return_none=True) or []

    def get_bpp_dyscypliny_for_year(self, zrodlo, rok):
        """Pobiera kody dyscyplin BPP dla źródła i roku."""
        return set(
            zrodlo.dyscyplina_zrodla_set.filter(rok=rok).values_list(
                "dyscyplina__kod", flat=True
            )
        )

    def get_pbn_dyscypliny_kody(self, pbn_disciplines):
        """Konwertuje listę dyscyplin PBN na kody dyscyplin BPP.

        Args:
            pbn_disciplines: lista słowników z PBN, każdy zawiera pole 'code'
        """
        dyscypliny_kody = set()
        dyscypliny_cache = self._get_dyscypliny_cache()

        for disc_dict in pbn_disciplines:
            # Wyciągnij kod ze słownika
            code = disc_dict.get("code") if isinstance(disc_dict, dict) else disc_dict
            if not code:
                continue

            kod_bpp = normalize_kod_dyscypliny(str(code))
            if not kod_bpp:
                logger.warning(f"Nieprawidłowy kod dyscypliny PBN: {code}")
                continue
            # Sprawdź czy kod istnieje w BPP
            if kod_bpp in dyscypliny_cache:
                dyscypliny_kody.add(kod_bpp)
            else:
                logger.debug(f"Kod dyscypliny {kod_bpp} nie istnieje w BPP")

        return dyscypliny_kody

    def compare_zrodlo(self, zrodlo):
        """Porównuje pojedyncze źródło z danymi PBN.

        Returns:
            dict: Lokalne statystyki z tego porównania do agregacji.
        """
        local_stats = {
            "processed": 0,
            "points_discrepancies": 0,
            "discipline_discrepancies": 0,
            "skipped_no_pbn": 0,
            "skipped_no_data": 0,
            "errors": 0,
        }

        if not zrodlo.pbn_uid:
            local_stats["skipped_no_pbn"] = 1
            return local_stats

        journal = zrodlo.pbn_uid
        points_data = journal.value("object", "points", return_none=True) or {}
        pbn_disciplines = self.get_pbn_disciplines(journal)

        # Konwertuj kody PBN na BPP
        pbn_dyscypliny_kody = self.get_pbn_dyscypliny_kody(pbn_disciplines)

        # Sprawdź czy są jakiekolwiek dane do porównania
        valid_years = [rok for rok in points_data if int(rok) >= self.min_rok]
        if not valid_years:
            local_stats["skipped_no_data"] = 1
            return local_stats

        # Iteruj po latach z punktami PBN - per-source transaction
        with transaction.atomic():
            for rok_str in valid_years:
                try:
                    rok = int(rok_str)
                except ValueError:
                    continue

                pbn_punkty = points_data[rok_str].get("points")
                if pbn_punkty is not None:
                    pbn_punkty = Decimal(str(pbn_punkty))

                # Pobierz punkty BPP
                try:
                    punktacja = zrodlo.punktacja_zrodla_set.get(rok=rok)
                    bpp_punkty = punktacja.punkty_kbn
                except Punktacja_Zrodla.DoesNotExist:
                    bpp_punkty = None

                # Pobierz dyscypliny BPP dla tego roku
                bpp_dyscypliny = self.get_bpp_dyscypliny_for_year(zrodlo, rok)

                # Sprawdź rozbieżności
                ma_rozbieznosc_punktow = bpp_punkty != pbn_punkty
                ma_rozbieznosc_dyscyplin = bpp_dyscypliny != pbn_dyscypliny_kody

                if ma_rozbieznosc_punktow or ma_rozbieznosc_dyscyplin:
                    RozbieznoscZrodlaPBN.objects.update_or_create(
                        zrodlo=zrodlo,
                        rok=rok,
                        defaults={
                            "ma_rozbieznosc_punktow": ma_rozbieznosc_punktow,
                            "punkty_bpp": bpp_punkty,
                            "punkty_pbn": pbn_punkty,
                            "ma_rozbieznosc_dyscyplin": ma_rozbieznosc_dyscyplin,
                            "dyscypliny_bpp": ",".join(sorted(bpp_dyscypliny)),
                            "dyscypliny_pbn": ",".join(sorted(pbn_dyscypliny_kody)),
                        },
                    )

                    if ma_rozbieznosc_punktow:
                        local_stats["points_discrepancies"] += 1
                    if ma_rozbieznosc_dyscyplin:
                        local_stats["discipline_discrepancies"] += 1
                else:
                    # Usuń ewentualną starą rozbieżność
                    RozbieznoscZrodlaPBN.objects.filter(zrodlo=zrodlo, rok=rok).delete()

        local_stats["processed"] = 1
        return local_stats

    def _process_single_zrodlo(self, zrodlo):
        """Przetwarza pojedyncze źródło - wywoływane z thread pool."""
        try:
            return self.compare_zrodlo(zrodlo)
        except Exception as e:
            logger.error(f"Błąd podczas porównywania źródła {zrodlo.pk}: {e}")
            return {
                "processed": 0,
                "points_discrepancies": 0,
                "discipline_discrepancies": 0,
                "skipped_no_pbn": 0,
                "skipped_no_data": 0,
                "errors": 1,
            }

    def _save_meta_completed(self, meta):
        """Zapisuje meta jako zakończone."""
        meta.ostatnie_uruchomienie = timezone.now()
        meta.status = "completed"
        meta.statystyki = self.stats
        meta.ostatni_blad = ""
        meta.save()

    def _process_future_result(self, future, future_to_zrodlo):
        """Przetwarza wynik future i aktualizuje statystyki."""
        zrodlo = future_to_zrodlo[future]
        try:
            local_stats = future.result()
            for key, value in local_stats.items():
                self._increment_stat(key, value)
        except Exception as e:
            logger.error(f"Błąd podczas porównywania źródła {zrodlo}: {e}")
            self._increment_stat("errors")

    def _run_parallel_processing(self, zrodla, total):
        """Wykonuje równoległe przetwarzanie źródeł."""
        max_workers = min(8, os.cpu_count() or 4)
        processed_count = 0

        logger.info(f"Przetwarzanie {total} źródeł z {max_workers} workerami")

        pbar = (
            tqdm(total=total, desc="Porównywanie źródeł")
            if self.show_progress
            else None
        )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_zrodlo = {
                executor.submit(self._process_single_zrodlo, zrodlo): zrodlo
                for zrodlo in zrodla
            }

            for future in as_completed(future_to_zrodlo):
                self._process_future_result(future, future_to_zrodlo)
                processed_count += 1

                if pbar:
                    pbar.update(1)

                if processed_count % 10 == 0 or processed_count == total:
                    if self.progress_callback:
                        self.progress_callback(processed_count, total, self.stats)

        if pbar:
            pbar.close()

    def run(self):
        """Główna metoda uruchamiająca porównanie (równoległe przetwarzanie)."""
        logger.info("Rozpoczynam porównywanie źródeł BPP-PBN (parallel)")

        meta = KomparatorZrodelMeta.get_instance()
        meta.status = "running"
        meta.save()

        try:
            if self.clear_existing:
                self.clear_discrepancies()

            self._get_dyscypliny_cache()

            zrodla = list(
                Zrodlo.objects.exclude(pbn_uid_id=None).select_related("pbn_uid")
            )
            total = len(zrodla)

            if total == 0:
                self._save_meta_completed(meta)
                logger.info("Brak źródeł do porównania.")
                return self.stats

            self._run_parallel_processing(zrodla, total)
            self._save_meta_completed(meta)

        except Exception as e:
            meta.status = "error"
            meta.ostatni_blad = str(e)
            meta.save()
            raise

        logger.info(f"Zakończono porównywanie. Statystyki: {self.stats}")
        return self.stats


def porownaj_zrodla_pbn(
    min_rok=2022, clear_existing=False, show_progress=True, progress_callback=None
):
    """
    Funkcja pomocnicza do uruchamiania porównania źródeł.

    Args:
        min_rok: Minimalny rok do porównania (domyślnie 2022)
        clear_existing: Czy wyczyścić istniejące rozbieżności przed porównaniem
        show_progress: Czy pokazywać pasek postępu tqdm (dla CLI)
        progress_callback: Callback wywoływany z (current, total, stats) dla aktualizacji postępu

    Returns:
        dict: Statystyki porównania
    """
    komparator = KomparatorZrodelPBN(
        min_rok=min_rok,
        clear_existing=clear_existing,
        show_progress=show_progress,
        progress_callback=progress_callback,
    )
    return komparator.run()
