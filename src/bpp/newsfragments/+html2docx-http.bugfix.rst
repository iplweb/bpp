Fallback konwersji DOCX (html2docx) działa teraz przez usługę HTTP zamiast
uruchamiania kontenera przez ``docker.sock``. Appserver nie potrzebuje już
dostępu do demona Dockera hosta ani Docker CLI w obrazie — usuwa to ryzyko,
w którym błąd w aplikacji dawałby kontrolę nad całym hostem. Adres usługi
podaje zmienna środowiskowa ``DJANGO_BPP_HTML2DOCX_URL`` (brak = fallback
wyłączony, degradacja miękka).
