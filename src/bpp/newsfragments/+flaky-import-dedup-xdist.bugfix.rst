Ustabilizowano flaky testy pod shardingiem (pytest-split + xdist). Pod
obciążeniem CI test commitujący dane poza rollback zostawiał w bazie workera
ambient autorów/jednostek/stopni/stanowisk, przez co kolejne testy pękały na
unikalnym constraincie (``bpp_jednostka_nazwa_key`` itp.) albo na asercjach
„pusta baza". Dodano defensywny guard izolacji w ``src/conftest.py``, który
przed każdym testem czyści wyciekłe dane domenowe (TRUNCATE tabel pustych w
baseline, bez ruszania danych referencyjnych). Dodatkowo testy
``import_pracownikow`` używają globalnie unikalnych nazw jednostek, a test
wykrywania duplikatów autorów asertuje inwariantę klastra zamiast globalnej
liczby kandydatów.
