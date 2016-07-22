rebuilddb:
	-dropdb bpp
	-dropdb test_bpp
	createdb bpp
	python manage.py makemigrations
	python manage.py migrate
	-say "Przebudowa bazy danych zakończona"
	-noti -t "rebuilddb zakończono" -m "Proces przebudowania bazy danych zakończony"

egeria-db-and-test:
	-dropdb test_bpp
	python manage.py makemigrations
	python manage.py migrate
	py.test egeria/tests.py