from import_common.core import matchuj_zrodlo
from import_list_ministerialnych.models import ImportListMinisterialnych
from import_list_ministerialnych.util import (
    napraw_literowki_w_bazie,
    wczytaj_plik_importu_dyscyplin_zrodel,
)

from bpp.models import Dyscyplina_Naukowa


def analyze_excel_file_import_list_ministerialnych(
    fn, parent_model: ImportListMinisterialnych
):
    napraw_literowki_w_bazie()
    data = wczytaj_plik_importu_dyscyplin_zrodel(fn)
    total = len(data)

    dry_run = not parent_model.zapisz_zmiany_do_bazy
    rok = parent_model.rok

    for nr_wiersza, elem in enumerate(data, 3):
        parent_model.send_progress(nr_wiersza * 100.0 / total)

        tytul_zrodla = elem["Tytul_1"] or elem["Tytul_2"]
        zrodlo = matchuj_zrodlo(
            tytul_zrodla,
            # alt_nazwa=elem["Tytuł 2"],
            issn=elem["issn"] or elem["issn.1"],
            e_issn=elem["e-issn"] or elem["e-issn.1"],
            disable_fuzzy=True,
            disable_skrot=True,
        )

        if zrodlo is None:
            if not parent_model.ignoruj_zrodla_bez_odpowiednika:
                parent_model.wierszimportulistyministerialnej_set.create(
                    nr_wiersza=nr_wiersza,
                    dane_z_xls=elem,
                    rezultat="Brak takiego źródła po stronie BPP",
                )
            continue

        try:
            punktacja = elem["Punkty"]
        except KeyError:
            punktacja = elem["Punktacja"]

        operacje = []

        if parent_model.importuj_punktacje:

            # Jest źródło. Sprawdźmy, czy ma punkty za dany rok:
            if zrodlo.punktacja_zrodla_set.filter(rok=rok).exists():
                # Istnieje, sprawdźmy, czy różna:
                pz = zrodlo.punktacja_zrodla_set.get(rok=rok)
                if pz.punkty_kbn != punktacja:
                    operacje.append(
                        f"Różna punktacja (BPP: {pz.punkty_kbn}, XLS {punktacja}), ustawiam na XLS. "
                    )
                    pz.punkty_kbn = punktacja
                    if not dry_run:
                        pz.save(update_fields=["punkty_kbn"])
                else:
                    operacje.append("Punktacja identyczna w BPP i w XLS")
            else:
                operacje.append(f"Ustawiam punktację {punktacja}. ")
                if not dry_run:
                    zrodlo.punktacja_zrodla_set.create(
                        rok=parent_model.rok, punkty_kbn=punktacja
                    )

        if parent_model.importuj_dyscypliny:
            # Sprawdź, czy wszystkie dyscypliny zakodowane w pliku XLSX występują w BPP
            dyscypliny_xlsx = set()
            for nazwa_dyscypliny in list(elem.keys())[9:]:
                if elem[nazwa_dyscypliny] == "x":
                    try:
                        dyscyplina_naukowa = Dyscyplina_Naukowa.objects.get(
                            nazwa=nazwa_dyscypliny
                        )
                        dyscypliny_xlsx.add(dyscyplina_naukowa.nazwa)
                    except Dyscyplina_Naukowa.DoesNotExist:
                        operacje.append(
                            f"Dyscyplina o nazwie '{nazwa_dyscypliny}' nie występuje w BPP. "
                        )

            # Aktualne dyscypliny:
            dyscypliny_bpp = {
                x.dyscyplina.nazwa for x in zrodlo.dyscyplina_zrodla_set.filter(rok=rok)
            }

            # Roznica:
            trzeba_usunac = dyscypliny_bpp.difference(dyscypliny_xlsx)
            trzeba_dodac = dyscypliny_xlsx.difference(dyscypliny_bpp)

            if not trzeba_dodac and not trzeba_usunac:
                operacje.append("Dyscypliny zgodne w BPP i w XLSX")
            else:
                dyscypliny_dodane = []
                for nazwa_dyscypliny in trzeba_dodac:
                    dyscypliny_dodane.append(nazwa_dyscypliny)
                    if not dry_run:
                        zrodlo.dyscyplina_zrodla_set.create(
                            rok=rok,
                            dyscyplina=Dyscyplina_Naukowa.objects.get(
                                nazwa=nazwa_dyscypliny
                            ),
                        )
                dyscypliny_usuniete = []
                for nazwa_dyscypliny in trzeba_usunac:
                    dyscypliny_usuniete.append(nazwa_dyscypliny)
                    if not dry_run:
                        zrodlo.dyscyplina_zrodla_set.get(
                            rok=rok,
                            dyscyplina=Dyscyplina_Naukowa.objects.get(
                                nazwa=nazwa_dyscypliny
                            ),
                        ).delete()

                if dyscypliny_dodane:
                    operacje.append(
                        "Dyscypliny dodane: " + ", ".join(dyscypliny_dodane) + ". "
                    )

                if dyscypliny_usuniete:
                    operacje.append(
                        "Dyscypliny wykreślone: "
                        + ", ".join(dyscypliny_usuniete)
                        + ". "
                    )

        parent_model.wierszimportulistyministerialnej_set.create(
            nr_wiersza=nr_wiersza,
            dane_z_xls=elem,
            zrodlo=zrodlo,
            rezultat="".join(operacje),
        )
