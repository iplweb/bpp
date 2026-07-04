"""Pageable resource handling for PBN API."""


class PageableResource:
    """Handles paginated responses from PBN API."""

    def __init__(self, transport, res, url, headers, body=None, method="get"):
        self.url = url
        self.headers = headers
        self.transport = transport
        self.body = body
        self.method = getattr(transport, method)

        try:
            self.page_0 = res["content"]
        except KeyError:
            self.page_0 = []

        self.current_page = res["number"]
        self.total_elements = res["totalElements"]
        self.total_pages = res["totalPages"]
        self.done = False

    def count(self):
        return self.total_elements

    def fetch_page(self, current_page):
        if current_page == 0:
            return self.page_0

        kw = {"headers": self.headers}
        if self.body:
            kw["body"] = self.body

        ret = self.method(self.url + f"&page={current_page}", **kw)

        try:
            return ret["content"]
        except KeyError:
            return

    def __iter__(self):
        for n in range(0, self.total_pages):
            yield from self.fetch_page(n)
