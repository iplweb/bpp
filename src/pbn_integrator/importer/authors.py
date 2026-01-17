"""Author processing for PBN importer."""

from bpp.models import Autor, Typ_Odpowiedzialnosci, Uczelnia
from pbn_integrator.utils import (
    pobierz_i_zapisz_dane_jednej_osoby,
    utworz_wpis_dla_jednego_autora,
)

from .helpers import assert_dictionary_empty


def _pobierz_lub_utworz_autora(pbn_uid_autora, client):
    """Fetch or create an author from PBN."""
    try:
        return Autor.objects.get(pbn_uid_id=pbn_uid_autora)
    except Autor.DoesNotExist:
        pbn_scientist = pobierz_i_zapisz_dane_jednej_osoby(
            client_or_token=client,
            personId=pbn_uid_autora,
            from_institution_api=False,
        )

        if (
            pbn_scientist.orcid
            and Autor.objects.filter(orcid=pbn_scientist.orcid).exists()
        ):
            print(
                f"UWAGA Wiecej niz jeden autor w PBNie ma TEN SAM ORCID: "
                f"{pbn_scientist.orcid=}"
            )
            print("ID autorow: ", pbn_scientist.pk, pbn_uid_autora)
            return Autor.objects.get(orcid=pbn_scientist.orcid)
        else:
            return utworz_wpis_dla_jednego_autora(pbn_scientist)


def _przetworz_afiliacje(
    ta_afiliacja,
    default_jednostka,
    typ_odpowiedzialnosci_autor,
    typ_odpowiedzialnosci_redaktor,
):
    """Process author affiliation data."""
    jednostka = Uczelnia.objects.default.obca_jednostka
    afiliuje = False
    typ_odpowiedzialnosci = typ_odpowiedzialnosci_autor

    if ta_afiliacja is None:
        return jednostka, afiliuje, typ_odpowiedzialnosci

    if isinstance(ta_afiliacja, list) and len(ta_afiliacja) == 1:
        ta_afiliacja = ta_afiliacja[0]
    else:
        jest_nasz = False
        typ_autora = ta_afiliacja[0]["type"]
        if ta_afiliacja[0]["institutionId"] == Uczelnia.objects.default.pbn_uid_id:
            jest_nasz = True
        for elem in ta_afiliacja[1:]:
            if elem["type"] != typ_autora:
                print(
                    f"UWAGA: autor w afiliacji -- jako kilka roznych typow "
                    f"{ta_afiliacja=}"
                )
                continue
            if elem["institutionId"] == Uczelnia.objects.default.pbn_uid_id:
                jest_nasz = True

        ta_afiliacja = {
            "type": typ_autora,
            "institutionId": (
                Uczelnia.objects.default.pbn_uid_id if jest_nasz else "123"
            ),
        }

    pbn_typ_odpowiedzialnosci = ta_afiliacja.pop("type")
    if pbn_typ_odpowiedzialnosci == "AUTHOR":
        typ_odpowiedzialnosci = typ_odpowiedzialnosci_autor
    elif pbn_typ_odpowiedzialnosci == "EDITOR":
        typ_odpowiedzialnosci = typ_odpowiedzialnosci_redaktor
    else:
        raise NotImplementedError(f"{pbn_typ_odpowiedzialnosci=}")

    pbn_institution_id = ta_afiliacja.pop("institutionId")

    if pbn_institution_id == Uczelnia.objects.default.pbn_uid_id:
        jednostka = default_jednostka
        afiliuje = True

    assert_dictionary_empty(ta_afiliacja)

    return jednostka, afiliuje, typ_odpowiedzialnosci


def utworz_autorow(ret, pbn_json, client, default_jednostka):
    wyliczona_kolejnosc = 0

    afiliacje = pbn_json.pop("affiliations", {})
    pbn_kolejnosci = pbn_json.pop("orderList", {})

    typ_odpowiedzialnosci_autor = Typ_Odpowiedzialnosci.objects.get(nazwa="autor")
    typ_odpowiedzialnosci_redaktor = Typ_Odpowiedzialnosci.objects.get(nazwa="redaktor")

    for (
        pbn_typ_odpowiedzialnosci,
        pbn_klucz_slownika_autorow,
        typ_odpowiedzialnosci,
    ) in [
        ("EDITOR", "editors", typ_odpowiedzialnosci_redaktor),
        ("AUTHOR", "authors", typ_odpowiedzialnosci_autor),
    ]:
        for pbn_uid_autora, pbn_autor in pbn_json.pop(
            pbn_klucz_slownika_autorow, {}
        ).items():
            autor = _pobierz_lub_utworz_autora(pbn_uid_autora, client)

            ta_afiliacja = afiliacje.pop(autor.pbn_uid_id, None)
            jednostka, afiliuje, typ_odpowiedzialnosci = _przetworz_afiliacje(
                ta_afiliacja,
                default_jednostka,
                typ_odpowiedzialnosci_autor,
                typ_odpowiedzialnosci_redaktor,
            )

            try:
                kolejnosc = pbn_kolejnosci.get(pbn_typ_odpowiedzialnosci, []).index(
                    autor.pbn_uid_id
                )
            except ValueError:
                kolejnosc = wyliczona_kolejnosc

            while ret.autorzy_set.filter(kolejnosc=kolejnosc).exists():
                kolejnosc += 1

            ret.autorzy_set.update_or_create(
                autor=autor,
                typ_odpowiedzialnosci=typ_odpowiedzialnosci,
                defaults=dict(
                    jednostka=jednostka,
                    kolejnosc=kolejnosc,
                    zapisany_jako=" ".join(
                        [
                            pbn_autor.pop("lastName", "") or "",
                            pbn_autor.pop("name", "") or "",
                        ]
                    ).strip(),
                    afiliuje=afiliuje,
                ),
            )

            wyliczona_kolejnosc += 1

            assert_dictionary_empty(pbn_autor)

    assert_dictionary_empty(afiliacje, warn=True)
