rebuilddb:
	dropdb bpp
	createdb bpp
	python manage.py makemigrations
	python manage.py migrate

egeria-db-and-test:
	-dropdb test_bpp
	python manage.py makemigrations
	python manage.py migrate
	py.test egeria/tests.py
