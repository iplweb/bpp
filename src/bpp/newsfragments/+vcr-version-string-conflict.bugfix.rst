Naprawiono błąd testów VCR (``AttributeError: property
'_get_version_string' of 'VCRHTTPResponse' object has no setter``)
występujący po podniesieniu ``vcrpy`` do 8.1.1. W ``conftest.py``
usunięto workaround rejestrujący ``version_string`` jako
read-only ``property`` — nowa wersja ``vcrpy`` ustawia ten atrybut
natywnie w ``VCRHTTPResponse.__init__``, a stary shim kolidował
z tą inicjalizacją.
