import json
import multiprocessing as mp
import pickle
import sys
from collections import defaultdict
from decimal import Decimal
from itertools import islice, product

import django
from tqdm import tqdm

django.setup()
from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc

wersje = defaultdict(list)


def get_data_from_json(json_file):

    for line in tqdm(open(json_file).readlines()):
        line = line.strip()
        if not line:
            continue

        if line == "---":
            continue

        if line == "[]":
            continue

        _l = line.replace("'", '"').lower().replace("decimal(", "").replace("),", ",")
        # print(f"[{l=}]")
        data = json.loads(_l)
        if not data:
            continue

        key = (int(data[0]["content_type"]), int(data[0]["record_id"]))
        wersje[key].append([data])

    for _key, items in wersje.items():
        items.append([])

    return wersje


def batch_generator(iterator, batch_size):
    """Generate batches from an iterator without materializing the entire sequence."""
    iterator = iter(iterator)
    while True:
        batch = list(islice(iterator, batch_size))
        if not batch:
            break
        yield batch


def process_batch(args):
    """Process a batch of combinations and return the best result from this batch."""
    batch, iua_cache_data = args

    # Reconstruct the cache from the passed data - create simple namedtuple-like objects
    from collections import namedtuple

    CacheEntry = namedtuple(
        "CacheEntry", ["ilosc_udzialow", "ilosc_udzialow_monografie"]
    )
    iua_cache = {key: CacheEntry(*values) for key, values in iua_cache_data}

    local_najlepszy_przebieg = []
    local_najlepsza_suma = 0

    for elem in batch:
        ta_suma = defaultdict(Decimal)
        ten_przebieg = []

        for praca in elem:
            if not praca:
                continue

            praca = praca[0][0]

            autor_id = praca["autor_id"]
            dyscyplina_naukowa_id = praca["dyscyplina_ud"]
            slot = Decimal(praca["slot"])

            if (autor_id, dyscyplina_naukowa_id) not in iua_cache:
                continue

            if praca["typ_ogolny"] == "art" or (
                praca["typ_ogolny"] == "ksi" and praca["pkd_rekord"] == 200
            ):
                moze_wcisnac = iua_cache[
                    (autor_id, dyscyplina_naukowa_id)
                ].ilosc_udzialow - ta_suma.get(autor_id, Decimal("0"))

            else:
                moze_wcisnac = iua_cache[
                    (autor_id, dyscyplina_naukowa_id)
                ].ilosc_udzialow_monografie - ta_suma.get(autor_id, Decimal("0"))

            if praca["slot"] <= moze_wcisnac:
                ta_suma[autor_id] += slot
                ten_przebieg.append(praca)

        suma_przebiegu = sum([x["pkdaut"] for x in ten_przebieg])

        if suma_przebiegu > local_najlepsza_suma:
            local_najlepsza_suma = suma_przebiegu
            local_najlepszy_przebieg = ten_przebieg

    return local_najlepsza_suma, local_najlepszy_przebieg


def update_global_best(lock, shared_suma, shared_przebieg, local_suma, local_przebieg):
    """Thread-safe update of global best result."""
    with lock:
        if local_suma > shared_suma.value:
            shared_suma.value = local_suma
            # Convert to bytes for sharing
            shared_przebieg.value = pickle.dumps(local_przebieg)
            print(f"Nowa najlepsza suma: {local_suma} wszystkie dyscypliny.")


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: python test_multiprocessing.py <json_file> [num_processes] [batch_size]"
        )
        sys.exit(1)

    json_file = sys.argv[1]
    num_processes = int(sys.argv[2]) if len(sys.argv) > 2 else mp.cpu_count()
    batch_size = int(sys.argv[3]) if len(sys.argv) > 3 else 1000

    print(f"Using {num_processes} processes with batch size {batch_size}")

    # Load data
    print("Loading data from JSON...")
    wersje = get_data_from_json(json_file)

    # Prepare cache data for sharing
    print("Preparing cache data...")
    iua_cache = {
        (x.autor_id, x.dyscyplina_naukowa_id): x
        for x in IloscUdzialowDlaAutoraZaCalosc.objects.all()
    }

    # Convert cache objects to serializable format
    iua_cache_data = [
        ((key, (obj.ilosc_udzialow, obj.ilosc_udzialow_monografie)))
        for key, obj in iua_cache.items()
    ]

    # Global best tracking (no manager needed for better performance)
    global_najlepsza_suma = 0
    global_najlepszy_przebieg = []

    # Create the combinations generator
    combinations = product(*wersje.values())

    # Process batches with multiprocessing
    print("Starting multiprocessing...")

    with mp.Pool(num_processes) as pool:
        # Create batch generator and prepare arguments
        batch_args = []  # noqa
        batches = batch_generator(combinations, batch_size)

        # Collect batches for processing (limit to avoid memory issues)
        max_concurrent_batches = (
            num_processes * 2
        )  # Keep 2x processes worth of work queued
        pending_results = []
        batch_count = 0

        try:
            for batch in batches:
                batch_count += 1
                args = (batch, iua_cache_data)

                # Submit batch for processing
                result = pool.apply_async(process_batch, (args,))
                pending_results.append((batch_count, result))

                # Process completed results when we have too many pending
                if len(pending_results) >= max_concurrent_batches:
                    # Get the oldest result
                    batch_num, oldest_result = pending_results.pop(0)
                    local_suma, local_przebieg = oldest_result.get()

                    # Update global best
                    if local_suma > global_najlepsza_suma:
                        global_najlepsza_suma = local_suma
                        global_najlepszy_przebieg = local_przebieg
                        print(
                            f"Nowa najlepsza suma: {local_suma} wszystkie dyscypliny (batch {batch_num})"
                        )

                    if batch_num % 100 == 0:
                        print(
                            f"Processed {batch_num} batches, current best suma: {global_najlepsza_suma}"
                        )

            # Process remaining results
            for batch_num, result in pending_results:
                local_suma, local_przebieg = result.get()

                if local_suma > global_najlepsza_suma:
                    global_najlepsza_suma = local_suma
                    global_najlepszy_przebieg = local_przebieg
                    print(
                        f"Nowa najlepsza suma: {local_suma} wszystkie dyscypliny (batch {batch_num})"
                    )

        except KeyboardInterrupt:
            print("\nInterrupted by user. Terminating processes...")
            pool.terminate()
            pool.join()
            raise

    print("\nFinal results:")
    print(f"Najlepsza suma: {global_najlepsza_suma}")
    print(f"Najlepszy przebieg contains {len(global_najlepszy_przebieg)} items")
    print(f"Total batches processed: {batch_count}")

    return global_najlepsza_suma, global_najlepszy_przebieg


if __name__ == "__main__":
    najlepsza_suma, najlepszy_przebieg = main()
