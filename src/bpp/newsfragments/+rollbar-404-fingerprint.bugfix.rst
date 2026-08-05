Rollbar: błędy "nie znaleziono strony" (``Http404``) są teraz grupowane w jedno
zgłoszenie per serwer i widok, zamiast zakładać osobne zgłoszenie dla każdego
nieistniejącego adresu odwiedzonego przez roboty indeksujące. Przy okazji
zgłoszenia rozróżniają teraz uczelnie po adresie, pod którym faktycznie
wystąpiły — istotne przy instalacjach obsługujących wiele uczelni naraz.
