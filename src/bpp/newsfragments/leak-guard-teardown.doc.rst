Guard izolacji bazy pod xdist dostał drugą sondę — na teardownie testu, po
pełnej finalizacji fixture'ów. W przeciwieństwie do dotychczasowej sondy
setupowej (która wskazywała sprawcę heurystycznie, jako „poprzedni test DB")
ta wskazuje go wprost: brudne tabele na własnym teardownie znaczą, że
zostawił je ten właśnie test. ``BPP_LEAK_GUARD_STRICT=1`` zamienia raport
w twardy błąd.
