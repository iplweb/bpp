API ``/api/v1/patent/{id}/`` zwracało błąd 500 dla patentów z ustawionym
rodzajem prawa patentowego (goły ``RelatedField`` nie miał reprezentacji).
Pole ``rodzaj_prawa`` jest teraz serializowane jako jego nazwa.
