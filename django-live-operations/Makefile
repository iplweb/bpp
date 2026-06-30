.PHONY: test docs demo demo-text

test:
	uv run pytest

docs:
	uv run mkdocs build

demo:
	cd example && docker compose up --build

demo-text:
	cd example && RUNNER=eager uv run python manage.py migrate --run-syncdb --noinput \
	  && RUNNER=eager uv run python manage.py seed_demo \
	  && RUNNER=eager uv run python manage.py run_liveop demo.DemoImport
