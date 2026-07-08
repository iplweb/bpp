Upload punktacji źródła: wartości dziesiętne wpisane z przecinkiem (np.
``impact_factor`` = ``3,2``) nie wywalają już zapisu błędem 500 — przecinek
jest normalizowany do kropki. Dotyczy zarówno tworzenia, jak i nadpisywania
punktacji; wartość niepoprawna po normalizacji zwraca teraz czytelny błąd 400
zamiast 500.
