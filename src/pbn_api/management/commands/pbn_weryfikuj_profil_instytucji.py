from tqdm import tqdm

from pbn_api.client import PageableResource
from pbn_api.integrator.simple_page_getter import simple_page_getter
from pbn_api.management.commands.util import PBNBaseCommand
from pbn_api.models import Publication

from bpp.models import Rekord


class Command(PBNBaseCommand):
    """Pozwala na zweryfikowanie tego, co znajduje się na profilu instytucji. Realnie, zwraca
    w formacie CSV prace, których odpowiedników NIE ma w BPP, następnie wyszukuje rekordy
    o identycznym tytule i ewentualnie pokazuje, ze są w BPP (i jakie mają PBN UIDy)
    """

    def handle(
        self, app_id, app_token, base_url, user_token, command=None, *args, **options
    ):
        widziane = set()
        client = self.get_client(app_id, app_token, base_url, user_token)

        page_data: PageableResource = client.get_institution_publications(page_size=5)
        pages = simple_page_getter(client, page_data, skip_page_on_failure=True)

        print(
            "   Tytuł;Status PBN;PBN UID;DOI;Rok;BPP ID 1;BPP PBN ID 1;BPP ID 2;BPP PBN ID 2"
        )
        for data in tqdm(pages, desc="Przetwarzam...", total=page_data.total_pages):

            for elem in data:
                publicationId = elem["publicationId"]

                if (
                    publicationId not in widziane
                    and not Rekord.objects.filter(pbn_uid_id=publicationId).exists()
                ):
                    try:
                        p = Publication.objects.get(pk=publicationId)
                        title = p.title
                        res = f"{p.title};{p.status};{p.pk};{p.doi or ''};{p.year};"
                    except Publication.DoesNotExist:
                        res = client.get_publication_by_id(publicationId)
                        current_version = [
                            version for version in res["versions"] if version["current"]
                        ][0]["object"]

                        title = current_version["title"]
                        doi = current_version.get("doi", "")
                        year = current_version.get("year", "")

                        res = f"{title};{res['status']};{publicationId};{doi};{year};"

                    duble = Rekord.objects.filter(tytul_oryginalny__icontains=title)
                    if duble.exists():
                        for elem in duble:
                            res += (
                                str(elem.pk) + ";" + str(elem.pbn_uid_id or "---") + ";"
                            )

                    res = res.replace("\n", " ").strip()
                    while res.find("  ") >= 0:
                        res = res.replace("  ", " ")
                    print(res)
                    widziane.add(publicationId)
