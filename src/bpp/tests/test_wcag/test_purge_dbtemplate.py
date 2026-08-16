"""Osierocony wiersz dbtemplate dla wariantu opisu bibliograficznego.

``browse/praca_tabela.html`` to alternatywny szablon opisu, zainstalowany
do ``dbtemplates`` migracją 0295. Migracja 0473 sprzątała dbtemplates, ale
tylko dla nazw wskazywanych przez ``SzablonDlaOpisuBibliograficznego``
— ten wariant nie był wskazywany, więc jego wiersz przetrwał.

Loader dbtemplates stoi przed plikowym, więc dopóki wiersz istnieje,
edycje szablonu na dysku (m.in. znacznik ``lang`` z WCAG 3.1.2) nie mają
żadnego efektu na instalacji, która przełączy się na ten wariant.
"""

import pytest
from dbtemplates.models import Template
from django.template.loader import get_template


@pytest.mark.django_db
def test_wiersz_dbtemplate_wariantu_nie_istnieje():
    assert not Template.objects.filter(name="browse/praca_tabela.html").exists()


@pytest.mark.django_db
def test_wariant_laduje_sie_z_dysku_ze_znacznikiem_jezyka():
    # Po skasowaniu wiersza get_template czyta plik z repozytorium, więc
    # widzi filtr oznacz_jezyk dodany w Task 4.
    tpl = get_template("browse/praca_tabela.html")

    with open(tpl.origin.name, encoding="utf-8") as f:
        zrodlo = f.read()

    assert "oznacz_jezyk" in zrodlo
