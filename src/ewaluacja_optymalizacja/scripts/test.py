import json
import sys
from collections import defaultdict
from decimal import Decimal
from itertools import product

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


iua_cache = {
    (x.autor_id, x.dyscyplina_naukowa_id): x
    for x in IloscUdzialowDlaAutoraZaCalosc.objects.all()
}

najlepszy_przebieg = []
najlepsza_suma = 0

wersje = get_data_from_json(sys.argv[1])

for elem in tqdm(product(*wersje.values())):
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

    if suma_przebiegu > najlepsza_suma:
        najlepsza_suma = suma_przebiegu
        najlepszy_przebieg = ten_przebieg
        tqdm.write(f"Nowa najlepsza suma: {suma_przebiegu} wszystkie dyscypliny.")
