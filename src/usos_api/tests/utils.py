"""Atrapy HTTP do testów klienta USOS API.

Klient przyjmuje sesję przez konstruktor (dependency injection), więc testy
nie potrzebują biblioteki mockującej ruch sieciowy — wystarczy podstawić
obiekt o interfejsie ``.get(url, params=..., timeout=..., auth=...)``.
"""


class FakeResponse:
    def __init__(self, dane, status_code=200, text=None):
        self._dane = dane
        self.status_code = status_code
        self.text = text if text is not None else str(dane)

    def json(self):
        if self._dane is None:
            raise ValueError("Brak treści JSON")
        return self._dane


class FakeSession:
    """Oddaje przygotowane odpowiedzi po kolei, zapisując wywołania."""

    def __init__(self, *odpowiedzi):
        self.odpowiedzi = list(odpowiedzi)
        self.wywolania = []

    def get(self, url, params=None, timeout=None, auth=None):
        self.wywolania.append({"url": url, "params": params or {}, "auth": auth})
        if not self.odpowiedzi:
            raise AssertionError(
                f"Nieoczekiwane wywołanie {url} z {params} — brak przygotowanej "
                f"odpowiedzi"
            )
        return self.odpowiedzi.pop(0)
