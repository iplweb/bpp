from pbn_api.client import PageableResource, PBNClient


def simple_page_getter(
    client: PBNClient,
    data: PageableResource,
):
    for n in range(data.total_pages):
        yield data.fetch_page(n)
