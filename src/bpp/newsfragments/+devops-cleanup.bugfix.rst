Uporządkowano konfigurację DevOps: usunięto martwy hook
``pre-commit-circleci`` (projekt używa GitHub Actions), skrócono
``start_period`` healthchecka serwisu ``appserver`` z 1800s do 120s,
dodano raportujący (non-blocking) skan obrazów Docker przez Trivy
w workflow ``build-docker-images.yml`` oraz zastąpiono
``filterwarnings = ignore`` w ``pytest.ini`` trybem ``default``
z wąskimi wyjątkami dla znanego szumu z bibliotek zewnętrznych,
tak aby realne ostrzeżenia (np. ``USE_L10N`` z Django) były widoczne.
