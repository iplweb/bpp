"""Faza B / issue #438 — I-4 (NAJTRUDNIEJSZE B-I).

Ustawienie FAKTYCZNEJ struktury drzewa `Jednostka`:

0. PROMOCJA jedno-jednostkowych wydziałów (#438): wydział z DOKŁADNIE JEDNĄ
   jednostką NIE dostaje pustej wydmuszki-lustra — jego jedyna jednostka jest
   promowana do ROOTA (`parent=None`), a węzeł-lustro usuwany (CASCADE sprząta
   wpisy `Jednostka_Rodzic`). Robione PRZED snapshotem/re-parentem, bo promocja
   odpina (org-)rodzica; usunięcie lustra przed krokami 2–4 (iterują po
   `legacy_wydzial_id__isnull=False`) gwarantuje brak wiszących FK.
1. SNAPSHOT sub-jednostek (parent NOT NULL, wydzial_id NOT NULL) PRZED
   re-parentem — krok 2 zmienia `parent` i zatarłby rozróżnienie.
2. Re-parent PŁASKICH jednostek (parent IS NULL, wydzial_id NOT NULL) pod
   węzeł-wydział (`legacy_wydzial_id == wydzial_id`). Węzły-wydziały (rooty)
   i sieroty (wydzial_id NULL) zostają rootami.
3. Własny wpis historii węzła-wydziału: `Jednostka_Rodzic(jednostka=węzeł,
   parent=None, od=Wydzial.otwarcie, do=CLAMP(Wydzial.zamkniecie))`.
   CLAMP: `zamkniecie >= dziś` → `do=None` (CHECK `do < NOW()`); `otwarcie >
   zamkniecie` → log + `do=None` (GiST daterange wymaga `od <= do`).
   Idempotentny guard: nie twórz, gdy wpis (węzeł, parent IS NULL) już jest.
4. Przepisanie historii sub-jednostek (snapshot!) na krawędź FAKTYCZNEGO
   (MPTT) rodzica z zachowaniem `od`/`do`. Direct-children NIETKNIĘTE.
   Patologia (wiele RÓŻNYCH wydziałów przy niezmiennym MPTT-rodzicu) →
   log + SKIP (NIE zgaduj przepisania).
5. Przeliczenie nested-set (`lft`/`rght`/`tree_id`/`level`) w czystym
   Pythonie (DFS per drzewo) — historical model nie ma `objects.rebuild()`.

Idempotencja: parent już ustawiony → krok 2 no-op; wpisy węzłów → guard;
przepisania sub-jednostek → no-op (parent już = MPTT rodzic); nested-set
przeliczalny wielokrotnie. `reverse_code=noop`.
"""

from datetime import date

from django.db import migrations


def _promuj_jednoelementowe_wydzialy(apps):
    """Krok 0 (#438): wydział z DOKŁADNIE JEDNĄ jednostką → promocja tej
    jednostki do ROOTA zamiast pustej wydmuszki-lustra.

    Identyfikacja (przesądzona przez właściciela): liczba jednostek wydziału W
    = ``Jednostka.objects.filter(wydzial_id=W.id)`` na etapie PRZED retargetem
    (0459) — ``wydzial_id`` to wciąż stary FK→Wydzial, a węzeł-lustro ma
    ``wydzial_id NULL`` (dodatkowo wykluczone przez ``legacy_wydzial_id
    IS NULL``), więc nie liczy się do swojego wydziału. ``== 1`` → promuj.

    Jednostka może być PŁASKA (``parent IS NULL``) albo mieć ORG-RODZICA
    (``parent`` wskazuje jednostkę spoza wydziału). W OBU wypadkach ustawiamy
    ``parent=None`` — jawne życzenie właściciela: promocja ODPINA od
    org-rodzica.

    Spójność (ŻADNYCH wiszących FK): usuwamy węzeł-lustro ``.delete()`` —
    CASCADE na ``Jednostka_Rodzic.parent`` i ``Jednostka_Rodzic.jednostka``
    kasuje wpisy WSKAZUJĄCE lustro (naiwny backfill 0456 wycelował je w lustro)
    ORAZ ewentualny własny wpis lustra; ``Jednostka.wydzial`` (SET_NULL) zeruje
    denorm. Jedyna jednostka jest odpięta PRZED usunięciem, więc lustro jest
    bezdzietne i CASCADE po ``Jednostka.parent`` nie tknie realnych jednostek.
    Lustro znika PRZED krokami 2–4 (iterują po ``legacy_wydzial_id__isnull=
    False``) → nie powstaje wpis historii lustra (krok 3) ani przepisanie po
    nieistniejącym lustrze (krok 4).

    Idempotentne: uruchamiane jako krok 0 (przed re-parentem); po pierwszym
    przebiegu 1-elementowe lustra już nie istnieją, a re-parent NIE zmienia
    ``wydzial_id``, więc ponowny przebieg nie promuje błędnie wydziałów ≥2.
    """
    Jednostka = apps.get_model("bpp", "Jednostka")

    # Materializacja listy PRZED pętlą — kasujemy lustra w trakcie iteracji.
    for mirror in list(Jednostka.objects.filter(legacy_wydzial_id__isnull=False)):
        czlonkowie = Jednostka.objects.filter(
            wydzial_id=mirror.legacy_wydzial_id,
            legacy_wydzial_id__isnull=True,
        )
        if czlonkowie.count() != 1:
            continue
        jedyna = czlonkowie.get()
        # Promocja do roota — ODPIĘCIE od (org-)rodzica, jeśli był. ``update``
        # (nie ``save``) omija sygnały/denorm; nested-set przelicza krok 5.
        Jednostka.objects.filter(pk=jedyna.pk).update(parent_id=None)
        # Usuń lustro: CASCADE sprząta wpisy Jednostka_Rodzic wskazujące lustro
        # (i własny wpis lustra), SET_NULL zeruje denorm ``wydzial``.
        mirror.delete()


def _reparent_plaskie(apps):
    """Krok 2: płaskie jednostki (parent IS NULL, wydzial_id NOT NULL) pod
    węzeł-wydział o `legacy_wydzial_id == wydzial_id`. Bulk update per
    wydział. Węzłów-wydziałów (legacy_wydzial_id NOT NULL) i sierot
    (wydzial_id NULL) nie ruszamy."""
    Jednostka = apps.get_model("bpp", "Jednostka")

    mapa = dict(
        Jednostka.objects.filter(legacy_wydzial_id__isnull=False).values_list(
            "legacy_wydzial_id", "id"
        )
    )
    for legacy_id, node_id in mapa.items():
        Jednostka.objects.filter(
            parent__isnull=True,
            wydzial_id=legacy_id,
            legacy_wydzial_id__isnull=True,
        ).update(parent_id=node_id)


def _wpis_historii_wezlow(apps):
    """Krok 3: dla każdego węzła-wydziału twórz własny wpis historii
    (`parent=None`, `od=otwarcie`, `do=CLAMP(zamkniecie)`). Idempotentny."""
    Jednostka = apps.get_model("bpp", "Jednostka")
    Jednostka_Rodzic = apps.get_model("bpp", "Jednostka_Rodzic")
    Wydzial = apps.get_model("bpp", "Wydzial")

    dzis = date.today()
    wydzialy = {w.id: w for w in Wydzial.objects.all()}

    for node in Jednostka.objects.filter(legacy_wydzial_id__isnull=False):
        # Idempotentny guard: nie duplikuj wpisu z pustym rodzicem.
        if Jednostka_Rodzic.objects.filter(
            jednostka_id=node.pk, parent__isnull=True
        ).exists():
            continue

        wydzial = wydzialy.get(node.legacy_wydzial_id)
        if wydzial is None:
            print(
                f"[0457_faza_b_i4] węzeł {node.pk} ma legacy_wydzial_id="
                f"{node.legacy_wydzial_id}, ale Wydzial nie istnieje — "
                f"pomijam wpis historii"
            )
            continue

        od = wydzial.otwarcie
        zamkniecie = wydzial.zamkniecie
        if zamkniecie is None or zamkniecie >= dzis:
            do = None  # otwarty / clamp przyszłego zamknięcia (CHECK do<NOW)
        else:
            do = zamkniecie

        if od is not None and do is not None and od > do:
            print(
                f"[0457_faza_b_i4] węzeł {node.pk} (Wydzial {wydzial.id}): "
                f"otwarcie {od} > zamkniecie {do} — daterange niepoprawny, "
                f"ustawiam do=None"
            )
            do = None

        Jednostka_Rodzic.objects.create(jednostka_id=node.pk, parent=None, od=od, do=do)


def _przepisz_historie_subjednostek(apps, sub_parent_map):
    """Krok 4: dla sub-jednostek (snapshot `sub_parent_map`: pk → MPTT
    parent_id) przepisz wpisy `Jednostka_Rodzic` z węzła-wydziału na krawędź
    FAKTYCZNEGO (MPTT) rodzica, zachowując `od`/`do`.

    Patologia: sub-jednostka wskazująca w historii wiele RÓŻNYCH
    węzłów-wydziałów przy niezmiennym MPTT-rodzicu → log + SKIP.
    Direct-children (spoza snapshotu) NIETKNIĘTE."""
    Jednostka = apps.get_model("bpp", "Jednostka")
    Jednostka_Rodzic = apps.get_model("bpp", "Jednostka_Rodzic")

    mirror_ids = set(
        Jednostka.objects.filter(legacy_wydzial_id__isnull=False).values_list(
            "id", flat=True
        )
    )

    for sub_id, mptt_parent_id in sub_parent_map.items():
        if mptt_parent_id is None:
            continue  # obronnie — snapshot bierze tylko parent NOT NULL

        # Zbiór RÓŻNYCH węzłów-wydziałów w historii tej sub-jednostki.
        wydzial_parents = {
            pid
            for pid in Jednostka_Rodzic.objects.filter(jednostka_id=sub_id).values_list(
                "parent_id", flat=True
            )
            if pid in mirror_ids
        }

        if len(wydzial_parents) > 1:
            print(
                f"[0457_faza_b_i4] PATOLOGIA: sub-jednostka {sub_id} ma w "
                f"historii wiele różnych węzłów-wydziałów {wydzial_parents} "
                f"przy niezmiennym MPTT-rodzicu {mptt_parent_id} — "
                f"NIE przepisuję (do ręcznego przeglądu)"
            )
            continue

        for pid in wydzial_parents:  # 0 lub 1
            Jednostka_Rodzic.objects.filter(jednostka_id=sub_id, parent_id=pid).update(
                parent_id=mptt_parent_id
            )


def _przelicz_nested_set(apps):
    """Krok 5: nested-set (`lft`/`rght`/`tree_id`/`level`) w czystym Pythonie.
    `objects.rebuild()` niedostępny na historical model. `order_insertion_by`
    = `["kolejnosc", "nazwa"]`.

    Cała adjacencja wczytana raz do pamięci (bez N+1 SELECT-ów per węzeł),
    obchodzona jawnym stosem (bez limitu rekurencji), zapisywana `update()`
    per węzeł (każdy ma inne lft/rght/level/tree_id)."""
    Jednostka = apps.get_model("bpp", "Jednostka")

    # (id, parent_id) — posortowane wg order_insertion_by, więc dzieci danego
    # rodzica pojawiają się w kolejności drzewa.
    rows = list(
        Jednostka.objects.order_by("kolejnosc", "nazwa").values_list("id", "parent_id")
    )
    children = {}
    roots = []
    for node_id, parent_id in rows:
        if parent_id is None:
            roots.append(node_id)
        else:
            children.setdefault(parent_id, []).append(node_id)

    tree_id = 0
    for root in roots:
        tree_id += 1
        # Iteracyjny DFS. Wpis na stosie: (node_id, level, lft, iter dzieci).
        # `lft` przypisujemy przy wejściu; `rght` znamy dopiero po zejściu.
        counter = 1
        stack = [(root, 0, counter, iter(children.get(root, ())))]
        counter += 1
        while stack:
            node_id, level, node_lft, child_iter = stack[-1]
            next_child = next(child_iter, None)
            if next_child is not None:
                stack.append(
                    (
                        next_child,
                        level + 1,
                        counter,
                        iter(children.get(next_child, ())),
                    )
                )
                counter += 1
                continue
            # Wszystkie dzieci obejrzane — `rght` to bieżący licznik.
            Jednostka.objects.filter(pk=node_id).update(
                lft=node_lft, rght=counter, tree_id=tree_id, level=level
            )
            counter += 1
            stack.pop()


def apply_faza_b_i4(apps, schema_editor):
    """Orkiestracja kroków 0–5 w zadanej KOLEJNOŚCI."""
    Jednostka = apps.get_model("bpp", "Jednostka")

    # (0) #438: 1-elementowy wydział → promuj jednostkę do roota, bez wydmuszki.
    # PRZED snapshotem (krok 1): promocja odpina org-rodzica (parent=None), więc
    # promowana jednostka NIE może wpaść do snapshotu sub-jednostek (krok 4).
    _promuj_jednoelementowe_wydzialy(apps)

    # (1) SNAPSHOT sub-jednostek PRZED re-parentem (krok 2 zmienia parent).
    sub_parent_map = dict(
        Jednostka.objects.filter(
            parent__isnull=False, wydzial_id__isnull=False
        ).values_list("pk", "parent_id")
    )

    _reparent_plaskie(apps)  # (2)
    _wpis_historii_wezlow(apps)  # (3)
    _przepisz_historie_subjednostek(apps, sub_parent_map)  # (4)
    _przelicz_nested_set(apps)  # (5)


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0456_faza_b_i3"),
    ]

    operations = [
        migrations.RunPython(apply_faza_b_i4, reverse_code=migrations.RunPython.noop),
    ]
