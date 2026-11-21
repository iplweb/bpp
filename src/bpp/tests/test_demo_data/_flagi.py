"""Flaga wyłączająca dodatki create_demo_data (dwudyscyplinowcy, rzadsze
typy, celowe brudy, lustro PBN) — dla testów, które liczą
dokładne ilości obiektów z rdzenia generatora. Dodatki mają własne testy
(``test_dodatki.py``)."""

BEZ_DODATKOW = ("--bez-dodatkow",)
