import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import product
from multiprocessing import Manager
from typing import Iterator, List, Union

from django.db import connections, transaction
from tqdm import tqdm

from bpp.models import (
    Autor_Dyscyplina,
    Cache_Punktacja_Autora,
    Dyscyplina_Zrodla,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
)
from bpp.models.sloty.core import IPunktacjaCacher


def wersje_dyscyplin(
    wzca: Union[Wydawnictwo_Zwarte_Autor, Wydawnictwo_Ciagle_Autor],
) -> Iterator[Union[Wydawnictwo_Zwarte_Autor, Wydawnictwo_Ciagle_Autor]]:
    """
    Generuje iteracje rekordu autora z różnymi wariantami przypisania dyscyplin.

    Logika:
    1. Jeśli rekord ma dyscyplina_naukowa i autor ma status "N" lub "D" w danym roku:
       - Zwraca iterację z oryginalną dyscypliną (przypieta=True)
       - Zwraca iterację BEZ dyscypliny (przypieta=False)

    2. Sprawdza czy autor ma inne dyscypliny (subdyscypliny) w tym roku
    3. Dla wydawnictw zwartych: zwraca wszystkie dodatkowe dyscypliny
    4. Dla wydawnictw ciągłych: zwraca tylko te dyscypliny, które są w Zrodlo.dyscypliny_zrodla

    Args:
        wzca: Instancja Wydawnictwo_Zwarte_Autor lub Wydawnictwo_Ciagle_Autor

    Yields:
        Kopie rekordu z różnymi wariantami przypisania dyscyplin
    """
    from copy import deepcopy

    # Pobierz rok z rekordu wydawnictwa
    rok = wzca.rekord.rok

    # Sprawdź czy rekord ma dyscyplina_naukowa
    if (
        not wzca.dyscyplina_naukowa
        or not wzca.afiliuje
        or not wzca.jednostka.skupia_pracownikow
        or not wzca.przypieta
    ):
        return

    # Sprawdź status autora w danym roku (N lub D)
    try:
        autor_dyscyplina = Autor_Dyscyplina.objects.get(autor=wzca.autor, rok=rok)
    except Autor_Dyscyplina.DoesNotExist:
        return

    # Jeśli autor ma status "N" lub "D"
    if autor_dyscyplina.rodzaj_autora and autor_dyscyplina.rodzaj_autora.skrot in [
        "N",
        "D",
    ]:
        # 1. Zwróć rekord z oryginalną dyscypliną (przypieta=True)
        rekord_z_dyscyplina = deepcopy(wzca)
        rekord_z_dyscyplina.przypieta = True
        yield rekord_z_dyscyplina

        # 2. Zwróć rekord BEZ dyscypliny (przypieta=False)
        rekord_bez_dyscypliny = deepcopy(wzca)
        rekord_bez_dyscypliny.dyscyplina_naukowa = None
        rekord_bez_dyscypliny.przypieta = False
        yield rekord_bez_dyscypliny

        # 3. Sprawdź czy autor ma inne dyscypliny/subdyscypliny w tym roku
        inne_dyscypliny = set()

        # Główna dyscyplina
        if (
            autor_dyscyplina.dyscyplina_naukowa
            and autor_dyscyplina.dyscyplina_naukowa != wzca.dyscyplina_naukowa
        ):
            inne_dyscypliny.add(autor_dyscyplina.dyscyplina_naukowa)

        # Subdyscyplina
        if (
            autor_dyscyplina.subdyscyplina_naukowa
            and autor_dyscyplina.subdyscyplina_naukowa != wzca.dyscyplina_naukowa
        ):
            inne_dyscypliny.add(autor_dyscyplina.subdyscyplina_naukowa)

        # Dla każdej innej dyscypliny
        for inna_dyscyplina in inne_dyscypliny:
            if isinstance(wzca, Wydawnictwo_Zwarte_Autor):
                # Dla wydawnictw zwartych: zwróć wszystkie dodatkowe dyscypliny
                rekord_z_inna_dyscyplina = deepcopy(wzca)
                rekord_z_inna_dyscyplina.dyscyplina_naukowa = inna_dyscyplina
                rekord_z_inna_dyscyplina.przypieta = True
                yield rekord_z_inna_dyscyplina

            elif isinstance(wzca, Wydawnictwo_Ciagle_Autor):
                # Dla wydawnictw ciągłych: sprawdź czy dyscyplina jest w Zrodlo.dyscypliny_zrodla
                zrodlo = wzca.rekord.zrodlo
                if (
                    zrodlo
                    and Dyscyplina_Zrodla.objects.filter(
                        zrodlo=zrodlo, dyscyplina=inna_dyscyplina, rok=rok
                    ).exists()
                ):
                    rekord_z_inna_dyscyplina = deepcopy(wzca)
                    rekord_z_inna_dyscyplina.dyscyplina_naukowa = inna_dyscyplina
                    rekord_z_inna_dyscyplina.przypieta = True
                    yield rekord_z_inna_dyscyplina


def kombinacje_autorow_dyscyplin(
    rekord: Union[Wydawnictwo_Zwarte, Wydawnictwo_Ciagle],
) -> Iterator[List[Union[Wydawnictwo_Zwarte_Autor, Wydawnictwo_Ciagle_Autor]]]:
    """
    Generuje wszystkie możliwe kombinacje autorów z dyscyplinami dla danego rekordu.

    Funkcja:
    1. Pobiera wszystkich autorów danego rekordu
    2. Dla każdego autora wykorzystuje funkcję wersje_dyscyplin aby uzyskać wszystkie warianty
    3. Usuwa puste elementy z wyników
    4. Używa kombinatoryki (itertools.product) aby wygenerować wszystkie możliwe kombinacje

    Args:
        rekord: Instancja Wydawnictwo_Zwarte lub Wydawnictwo_Ciagle

    Yields:
        Lista reprezentująca jedną kombinację wszystkich autorów z przypisanymi dyscyplinami.
        Każda lista zawiera po jednym wariancie każdego autora z różnymi przypisaniami dyscyplin.
    """
    # Pobierz wszystkich autorów rekordu
    try:
        autorzy = rekord.autorzy_set.all()
    except AttributeError:
        # Rekord nie ma atrybutu autorzy_set (nieprawidłowy typ)
        return

    # Dla każdego autora pobierz wszystkie wersje dyscyplin
    wersje_dla_autorow = []

    for autor in autorzy:
        # Pobierz wszystkie wersje dyscyplin dla tego autora
        wersje_autora = list(wersje_dyscyplin(autor))

        # Usuń puste elementy (choć wersje_dyscyplin nie powinno ich zwracać)
        wersje_autora = [wersja for wersja in wersje_autora if wersja is not None]

        # Jeśli autor ma jakieś wersje, dodaj do listy
        if wersje_autora:
            wersje_dla_autorow.append(wersje_autora)

    # Jeśli nie ma żadnych wersji, zwróć pustą iterację
    if not wersje_dla_autorow:
        return

    # Użyj itertools.product do wygenerowania wszystkich kombinacji
    # product(*wersje_dla_autorow) generuje kartezjański iloczyn wszystkich list wersji
    for kombinacja in product(*wersje_dla_autorow):
        yield list(kombinacja)


def wszystkie_wersje_pracy(rekord: Wydawnictwo_Zwarte | Wydawnictwo_Ciagle):
    overs = list(kombinacje_autorow_dyscyplin(rekord))

    def foo(e):
        res = []
        with transaction.atomic():
            for ovs in elem:
                ovs.save()

            ipc = IPunktacjaCacher(rekord)
            ipc.removeEntries()
            ipc.rebuildEntries()
            for cpa in Cache_Punktacja_Autora.objects.filter(rekord_id=ipc.get_pk()):
                s = dict(
                    wydawnictwo_ciagle=isinstance(rekord, Wydawnictwo_Ciagle),
                    wydawnictwo_zwarte=isinstance(rekord, Wydawnictwo_Zwarte),
                    typ_ogolny=rekord.charakter_formalny.charakter_ogolny,
                    content_type=ipc.ctype,
                    record_id=rekord.pk,
                    autor_id=cpa.autor_id,
                    dyscyplina_ud=cpa.dyscyplina_id,
                    pkd_rekord=rekord.punkty_kbn,
                    pkdaut=cpa.pkdaut,
                    slot=cpa.slot,
                    avg_pkdaut_per_slot=cpa.pkdaut / cpa.slot,
                    rodzaj_autora=(
                        lambda ad: ad.rodzaj_autora.skrot if ad.rodzaj_autora else None
                    )(
                        Autor_Dyscyplina.objects.get(
                            autor_id=cpa.autor_id, rok=rekord.rok
                        )
                    ),
                )
                res.append(s)
            transaction.set_rollback(True)

        return res

    xres = []
    for elem in overs:
        # Lamerstwo totalne, idzie to wszystko przez bazę dancyh. Ale hej, idzie to przez sprawdzony
        # wieloletni przetestowany kod, zatem:
        xres.append(foo(elem))

    return xres


def safe_wszystkie_wersje_pracy(rekord):
    """
    Process-safe wrapper for wszystkie_wersje_pracy that ensures proper database connection handling.

    In multiprocessing environments, Django database connections cannot be shared between processes.
    This function ensures each process gets a fresh database connection by closing
    any existing connections before processing.

    Args:
        rekord: Wydawnictwo_Zwarte or Wydawnictwo_Ciagle record to process

    Returns:
        List of dictionaries containing scoring results for all author/discipline combinations
    """
    # Ensure clean database connections for this process
    connections.close_all()

    try:
        return wszystkie_wersje_pracy(rekord)
    finally:
        # Clean up connections after processing
        connections.close_all()


def process_record_batch(records):
    """
    Process a batch of records in a single process.

    This function is designed to be called by multiprocessing.ProcessPoolExecutor
    and returns a tuple of (results, processed_count) for progress tracking.

    Args:
        records: List of records to process

    Returns:
        Tuple of (results_list, processed_count)
    """
    results_list = []
    processed_count = 0

    for record in records:
        try:
            results = safe_wszystkie_wersje_pracy(record)
            results_list.extend(results)
            processed_count += 1

        except Exception as e:
            # Log the error but continue processing other records
            print(f"Error processing record {record.pk}: {e}")
            processed_count += 1

    return results_list, processed_count


class ProcessSafeProgressTracker:
    """
    Process-safe progress tracker that coordinates multiple tqdm progress bars across processes.

    This class allows multiple processes to update progress in a coordinated way,
    ensuring the progress display is coherent and doesn't interfere between processes.
    """

    def __init__(self, total_count, description="Processing"):
        self.total_count = total_count
        self.manager = Manager()
        self.processed_count = self.manager.Value("i", 0)
        self.lock = self.manager.Lock()
        self.pbar = tqdm(total=total_count, desc=description)

    def update(self, count=1):
        """Update progress by count items."""
        with self.lock:
            self.processed_count.value += count
            self.pbar.update(count)

    def close(self):
        """Close the progress bar."""
        self.pbar.close()


def wszystkie_wersje_rekordow(
    rok_min=2022,
    rok_max=2025,
    max_workers=None,
    batch_size=50,
    use_multiprocessing=True,
):
    """
    Process all publication records with optional multiprocessing support.

    Args:
        rok_min: Minimum year to process (default: 2022)
        rok_max: Maximum year to process (default: 2025)
        max_workers: Number of processes to use (default: CPU count)
        batch_size: Number of records per batch (default: 200)
        use_multiprocessing: Whether to use multiprocessing (default: True)

    Yields:
        Results from processing each publication record
    """
    # Determine worker count
    if max_workers is None:
        max_workers = int(2 * os.cpu_count()) or 1

    # Get all records to process
    ciagle_qs = Wydawnictwo_Ciagle.objects.filter(
        rok__gte=rok_min, rok__lte=rok_max, punkty_kbn__gt=0
    ).select_related()
    zwarte_qs = Wydawnictwo_Zwarte.objects.filter(
        rok__gte=rok_min, rok__lte=rok_max, punkty_kbn__gt=0
    ).select_related()

    # Get record counts
    ciagle_count = ciagle_qs.count()
    zwarte_count = zwarte_qs.count()
    total_count = ciagle_count + zwarte_count

    if not use_multiprocessing or max_workers == 1:
        # Single-process processing (original behavior)
        for elem in tqdm(ciagle_qs, desc="Processing Wydawnictwo_Ciagle"):
            yield from wszystkie_wersje_pracy(elem)

        for elem in tqdm(zwarte_qs, desc="Processing Wydawnictwo_Zwarte"):
            yield from wszystkie_wersje_pracy(elem)
        return

    # Multi-threaded processing
    def create_batches(queryset, batch_size):
        """Create batches of records for parallel processing."""
        records = list(queryset)
        for i in range(0, len(records), batch_size):
            yield records[i : i + batch_size]

    # Create progress tracker
    progress_tracker = ProcessSafeProgressTracker(
        total_count, "Processing publications"
    )

    try:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # Submit all batches to process pool
            future_to_batch = {}

            # Process Wydawnictwo_Ciagle
            for batch in create_batches(ciagle_qs, batch_size):
                future = executor.submit(process_record_batch, batch)
                future_to_batch[future] = ("ciagle", batch)

            # Process Wydawnictwo_Zwarte
            for batch in create_batches(zwarte_qs, batch_size):
                future = executor.submit(process_record_batch, batch)
                future_to_batch[future] = ("zwarte", batch)

            # Collect results as they complete
            for future in as_completed(future_to_batch):
                try:
                    batch_results, processed_count = future.result()
                    # Update progress tracker with the number of records processed
                    progress_tracker.update(processed_count)
                    # Yield each individual result
                    yield from batch_results
                except Exception as e:
                    batch_type, batch = future_to_batch[future]
                    print(f"Error processing {batch_type} batch: {e}")
                    # Still update progress for failed batch
                    progress_tracker.update(len(batch))

    finally:
        progress_tracker.close()
