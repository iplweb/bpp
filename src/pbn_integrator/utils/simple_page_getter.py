from pbn_api.client import PageableResource, PBNClient
from pbn_api.exceptions import HttpException


def simple_page_getter(
    client: PBNClient,
    data: PageableResource,
    repeat_on_failure: bool = False,
    skip_page_on_failure: bool = False,
):
    for n in range(data.total_pages):
        while True:
            try:
                yield data.fetch_page(n)
                break
            except HttpException as e:
                if skip_page_on_failure:
                    break

                if not repeat_on_failure:
                    raise e

                if e.status_code != 500:
                    raise e
