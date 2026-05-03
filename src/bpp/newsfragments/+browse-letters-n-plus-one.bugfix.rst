Strony przeglądania ``/bpp/browse/autorzy/``,
``/bpp/browse/zrodla/`` i ``/bpp/browse/jednostki/``
generują listę aktywnych literek alfabetu jednym zapytaniem
``SELECT DISTINCT`` zamiast 26+ osobnych ``EXISTS``-ów
(po jednym na każdą literkę z osobnym matchingiem dla
polskich znaków). Polskie diakrytyki nadal mapują się na
kanoniczne litery (``Ą`` → ``A``, ``Ł`` → ``L`` itd.).
