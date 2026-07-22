Reset przypięć dyscypliny nie blokuje już żądania HTTP. Wcześniej widok
mógł wisieć do 10 minut, śpiąc w pętli i odpytując globalny licznik
denormalizacji (czekając także na cudzą pracę). Teraz reset, oczekiwanie na
denormalizację i optymalizacja biegną w zadaniu Celery, a użytkownik jest
przekierowywany na stronę statusu z podglądem postępu.
