"""Focused unit tests for PBN import repair management commands."""

from io import StringIO
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

import pytest
from django.core.management.base import CommandError, OutputWrapper

from pbn_import.management.commands.fix_import_dat_oswiadczen_pbn import (
    Command as StatementDateCommand,
)
from pbn_import.management.commands.fix_missing_imported_pubs import (
    Command as MissingPublicationCommand,
)
from pbn_import.management.commands.fix_pbn_import_oswiadczen_ksiazki import (
    Command as BookStatementTypeCommand,
)


def make_command(command_cls):
    command = command_cls()
    command.stdout = OutputWrapper(StringIO())
    command.stderr = OutputWrapper(StringIO())
    return command


@pytest.mark.parametrize(
    "options,expected",
    [
        ({"rok": None, "rok_min": None, "rok_max": None}, None),
        ({"rok": 2024, "rok_min": None, "rok_max": None}, (2024, 2024)),
        ({"rok": None, "rok_min": 2022, "rok_max": 2025}, (2022, 2025)),
    ],
)
def test_statement_date_year_range(options, expected):
    command = make_command(StatementDateCommand)

    command._validate_year_parameters(options)

    assert command._get_year_range(options) == expected


@pytest.mark.parametrize(
    "options,message",
    [
        (
            {"rok": 2024, "rok_min": 2022, "rok_max": None},
            "Nie można używać --rok",
        ),
        (
            {"rok": None, "rok_min": 2022, "rok_max": None},
            "muszą być używane razem",
        ),
        (
            {"rok": None, "rok_min": 2025, "rok_max": 2022},
            "nie może być większy",
        ),
    ],
)
def test_statement_date_rejects_invalid_year_parameters(options, message):
    command = make_command(StatementDateCommand)

    with pytest.raises(CommandError, match=message):
        command._validate_year_parameters(options)


def test_statement_date_should_skip_by_year():
    command = make_command(StatementDateCommand)
    author_link = SimpleNamespace(rekord=SimpleNamespace(rok=2024))

    assert command._should_skip_by_year(author_link, None) is False
    assert command._should_skip_by_year(author_link, (2020, 2023)) is True
    assert command._should_skip_by_year(author_link, (2024, 2024)) is False


def test_statement_date_parser_accepts_repair_options():
    parser = make_command(StatementDateCommand).create_parser(
        "manage.py",
        "fix_import_dat_oswiadczen_pbn",
    )

    options = parser.parse_args(["--dry-run", "--nadpisz", "--rok", "2024"])

    assert options.dry_run is True
    assert options.nadpisz is True
    assert options.rok == 2024


def test_statement_date_print_config_info_for_dry_run_and_year_range():
    command = make_command(StatementDateCommand)

    command._print_config_info(dry_run=True, nadpisz=True, year_range=(2022, 2025))

    output = command.stdout._out.getvalue()
    assert "TRYB TESTOWY" in output
    assert "Lata do przetworzenia: 2022-2025" in output
    assert "Tryb nadpisywania" in output


def test_statement_date_print_config_info_for_all_years_without_overwrite():
    command = make_command(StatementDateCommand)

    command._print_config_info(dry_run=False, nadpisz=False, year_range=None)

    output = command.stdout._out.getvalue()
    assert "Przetwarzanie wszystkich lat" in output
    assert "Aktualizacja tylko rekordów z pustą datą" in output


def test_statement_date_summary_reports_missing_and_skipped_counts():
    command = make_command(StatementDateCommand)

    command._print_summary(
        updated_count=2,
        skipped_year_filter=3,
        skipped_existing_date=4,
        missing_publication=[("pub-1", "Title")],
        missing_autor=[("person-1", "Jan Kowalski")],
        missing_link=[("Book title", "Jan Kowalski", 2024, "pub-2")],
    )

    output = command.stdout._out.getvalue()
    assert "Zaktualizowano: 2" in output
    assert "Pominięto (brak powiązania): 3" in output
    assert "Pominięto (filtr roku): 3" in output
    assert "Pominięto (istniejąca data): 4" in output


def test_statement_date_missing_details_truncates_long_lists():
    command = make_command(StatementDateCommand)

    command._print_missing_details(
        list(range(16)),
        "Braki",
        lambda item: f"item-{item}",
    )

    output = command.stdout._out.getvalue()
    assert "Braki (16)" in output
    assert "item-0" in output
    assert "... i 1 więcej" in output


def test_missing_publication_prepare_list_applies_limit():
    command = make_command(MissingPublicationCommand)

    class FakeQuerySet:
        def __init__(self, items):
            self.items = items

        def count(self):
            return len(self.items)

        def __iter__(self):
            return iter(self.items)

    with patch.object(
        command,
        "get_missing_publications",
        return_value=FakeQuerySet([1, 2, 3]),
    ):
        missing_list, missing_count = command._prepare_missing_list({"limit": 2})

    assert missing_list == [1, 2]
    assert missing_count == 3


def test_missing_publication_prepare_list_accepts_list_from_type_filter():
    command = make_command(MissingPublicationCommand)

    with patch.object(command, "get_missing_publications", return_value=[1, 2, 3]):
        missing_list, missing_count = command._prepare_missing_list({"limit": None})

    assert missing_list == [1, 2, 3]
    assert missing_count == 3


def test_missing_publication_get_missing_publications_filters_by_uid():
    command = make_command(MissingPublicationCommand)
    rekord_qs = MagicMock()
    rekord_qs.exclude.return_value = rekord_qs
    rekord_qs.values_list.return_value = ["existing-pub"]
    missing_qs = MagicMock()

    with patch(
        "pbn_import.management.commands.fix_missing_imported_pubs.Rekord.objects"
    ) as rekordy:
        with patch(
            "pbn_import.management.commands.fix_missing_imported_pubs."
            "Publication.objects"
        ) as publications:
            rekordy.exclude.return_value = rekord_qs
            publications.exclude.return_value = missing_qs
            missing_qs.filter.return_value = "filtered"

            result = command.get_missing_publications(
                {"pbn_uid": "target-pub", "type": None}
            )

    assert result == "filtered"
    publications.exclude.assert_called_once_with(pk__in={"existing-pub"})
    missing_qs.filter.assert_called_once_with(pk="target-pub")


def test_missing_publication_get_missing_publications_filters_by_type():
    command = make_command(MissingPublicationCommand)
    rekord_qs = MagicMock()
    rekord_qs.exclude.return_value = rekord_qs
    rekord_qs.values_list.return_value = []
    article = SimpleNamespace(current_version={"object": {"type": "ARTICLE"}})
    book = SimpleNamespace(current_version={"object": {"type": "BOOK"}})
    without_version = SimpleNamespace(current_version=None)

    with patch(
        "pbn_import.management.commands.fix_missing_imported_pubs.Rekord.objects"
    ) as rekordy:
        with patch(
            "pbn_import.management.commands.fix_missing_imported_pubs."
            "Publication.objects"
        ) as publications:
            rekordy.exclude.return_value = rekord_qs
            publications.exclude.return_value = [article, book, without_version]

            result = command.get_missing_publications({"pbn_uid": None, "type": "BOOK"})

    assert result == [book]


def test_missing_publication_parser_accepts_repair_options():
    parser = make_command(MissingPublicationCommand).create_parser(
        "manage.py",
        "fix_missing_imported_pubs",
    )

    options = parser.parse_args(
        [
            "--dry-run",
            "--pbn-uid",
            "pub-1",
            "--type",
            "BOOK",
            "--limit",
            "5",
            "--max-errors",
            "2",
            "--verbose",
        ]
    )

    assert options.dry_run is True
    assert options.pbn_uid == "pub-1"
    assert options.type == "BOOK"
    assert options.limit == 5
    assert options.max_errors == 2
    assert options.verbose is True


def test_missing_publication_process_single_publication_imported():
    command = make_command(MissingPublicationCommand)
    publication = SimpleNamespace(
        pk="pub-1",
        mongoId="mongo-1",
        year=2024,
        current_version={"object": {"title": "Publication title"}},
    )

    with patch(
        "pbn_import.management.commands.fix_missing_imported_pubs."
        "import_publication_with_statements",
        return_value=("bpp-record", None, (2, 0)),
    ) as import_publication:
        status, data = command._process_single_publication(
            publication,
            client="client",
            default_jednostka="unit",
            rodzaj_periodyk="periodic",
            dyscypliny_cache={"discipline": "object"},
            verbose=False,
        )

    import_publication.assert_called_once_with(
        "mongo-1",
        "client",
        "unit",
        force=False,
        with_statements=True,
        rodzaj_periodyk="periodic",
        dyscypliny_cache={"discipline": "object"},
    )
    assert status == "imported"
    assert data == 2


def test_missing_publication_process_single_publication_error():
    command = make_command(MissingPublicationCommand)
    publication = SimpleNamespace(
        pk="pub-1",
        mongoId="mongo-1",
        year=2024,
        current_version={"object": {"title": "Publication title"}},
    )

    with patch(
        "pbn_import.management.commands.fix_missing_imported_pubs."
        "import_publication_with_statements",
        return_value=(None, {"message": "cannot import", "traceback": "tb"}, None),
    ):
        status, data = command._process_single_publication(
            publication,
            client="client",
            default_jednostka="unit",
            rodzaj_periodyk=None,
            dyscypliny_cache={},
            verbose=True,
        )

    assert status == "error"
    assert data == {
        "pbn_uid": "pub-1",
        "title": "Publication title",
        "year": 2024,
        "message": "cannot import",
        "traceback": "tb",
    }
    assert "Błąd dla pub-1" in command.stderr._out.getvalue()


def test_missing_publication_process_single_publication_skipped():
    command = make_command(MissingPublicationCommand)
    publication = SimpleNamespace(
        pk="pub-1",
        mongoId="mongo-1",
        year=2024,
        current_version=None,
    )

    with patch(
        "pbn_import.management.commands.fix_missing_imported_pubs."
        "import_publication_with_statements",
        return_value=(None, None, None),
    ):
        status, data = command._process_single_publication(
            publication,
            client="client",
            default_jednostka="unit",
            rodzaj_periodyk=None,
            dyscypliny_cache={},
            verbose=True,
        )

    assert status == "skipped"
    assert data is None
    assert "Pominięto: pub-1" in command.stdout._out.getvalue()


def test_missing_publication_dry_run_summary_reports_all_sections():
    command = make_command(MissingPublicationCommand)

    command._display_dry_run_summary(
        imported=2,
        skipped=3,
        errors=[{"pbn_uid": "pub-1"}],
        statements_total=4,
    )

    output = command.stdout._out.getvalue()
    assert "TRYB DRY-RUN" in output
    assert "Zaimportowano by: 2" in output
    assert "Oświadczeń by: 4" in output
    assert "Pominięto by: 3" in output
    assert "Błędów: 1" in output


def test_missing_publication_display_summary_reports_errors_and_traceback():
    command = make_command(MissingPublicationCommand)

    command._display_summary(
        imported=1,
        skipped=2,
        errors=[
            {
                "pbn_uid": "pub-1",
                "title": "Very long title " * 10,
                "year": 2024,
                "message": "cannot import",
                "traceback": "traceback text",
            }
        ],
        statements_total=3,
        stopped_early=True,
    )

    output = command.stdout._out.getvalue()
    assert "Zaimportowano: 1" in output
    assert "Oświadczeń: 3" in output
    assert "Pominięto: 2" in output
    assert "Import przerwany" in output
    assert "PBN UID: pub-1" in output
    assert "traceback text" in output


def test_missing_publication_handle_inner_returns_when_no_missing():
    command = make_command(MissingPublicationCommand)

    with patch.object(command, "_prepare_missing_list", return_value=([], 0)):
        command._handle_inner({"limit": None}, dry_run=False)

    assert "Wszystkie publikacje PBN" in command.stdout._out.getvalue()


def test_missing_publication_handle_inner_imports_and_displays_summary():
    command = make_command(MissingPublicationCommand)
    default_jednostka = SimpleNamespace(__str__=lambda self: "Default unit")

    with patch.object(command, "_prepare_missing_list", return_value=(["pub"], 1)):
        with patch(
            "pbn_import.management.commands.fix_missing_imported_pubs."
            "get_validated_default_jednostka",
            return_value=default_jednostka,
        ):
            with patch.object(command, "get_client", return_value="client"):
                with patch.object(
                    command,
                    "_import_publications",
                    return_value=(1, 0, [], 3, False),
                ) as import_publications:
                    with patch.object(command, "_display_summary") as display_summary:
                        command._handle_inner(
                            {
                                "limit": None,
                                "jednostka": None,
                                "app_id": "app-id",
                                "app_token": "app-token",
                                "base_url": "https://pbn.example.test",
                                "user_token": "user-token",
                                "verbose": False,
                            },
                            dry_run=False,
                        )

    import_publications.assert_called_once_with(
        ["pub"], "client", default_jednostka, ANY
    )
    display_summary.assert_called_once_with(1, 0, [], 3, False)


def test_book_statement_type_expected_type():
    command = make_command(BookStatementTypeCommand)
    typ_autor = SimpleNamespace(nazwa="autor")
    typ_redaktor = SimpleNamespace(nazwa="redaktor")

    assert (
        command._get_expected_typ(SimpleNamespace(type="AUTHOR"), typ_autor, typ_redaktor)
        is typ_autor
    )
    assert (
        command._get_expected_typ(SimpleNamespace(type="EDITOR"), typ_autor, typ_redaktor)
        is typ_redaktor
    )
    with pytest.raises(ValueError, match="Nieznany typ"):
        command._get_expected_typ(
            SimpleNamespace(type="TRANSLATOR"),
            typ_autor,
            typ_redaktor,
        )


def test_book_statement_type_parser_accepts_repair_options():
    parser = make_command(BookStatementTypeCommand).create_parser(
        "manage.py",
        "fix_pbn_import_oswiadczen_ksiazki",
    )

    options = parser.parse_args(
        [
            "--dry-run",
            "--verbose",
            "--publikacja",
            "pub-1",
            "--integruj-dyscypliny",
        ]
    )

    assert options.dry_run is True
    assert options.verbose is True
    assert options.publikacja == "pub-1"
    assert options.integruj_dyscypliny is True


def test_book_statement_type_print_config_info():
    command = make_command(BookStatementTypeCommand)

    command._print_config_info(
        {
            "dry_run": True,
            "publikacja": "pub-1",
            "integruj_dyscypliny": True,
        }
    )

    output = command.stdout._out.getvalue()
    assert "TRYB TESTOWY" in output
    assert "Przetwarzanie publikacji: pub-1" in output
    assert "Integracja dyscyplin: TAK" in output


def test_book_statement_type_print_config_info_for_all_books():
    command = make_command(BookStatementTypeCommand)

    command._print_config_info(
        {
            "dry_run": False,
            "publikacja": None,
            "integruj_dyscypliny": False,
        }
    )

    assert "Przetwarzanie wszystkich książek z PBN" in command.stdout._out.getvalue()


def test_book_statement_type_print_summary_reports_errors():
    command = make_command(BookStatementTypeCommand)

    command._print_summary(
        fixed_count=2,
        skipped_no_wa=3,
        skipped_matching=4,
        errors=[f"error-{index}" for index in range(12)],
    )

    output = command.stdout._out.getvalue()
    assert "Naprawiono: 2" in output
    assert "brak powiązania autor-publikacja): 3" in output
    assert "typ już zgodny): 4" in output
    assert "Błędy: 12" in output
    assert "... i 2 więcej" in output


def test_book_statement_type_get_books_queryset_filters_existing_publication():
    command = make_command(BookStatementTypeCommand)
    queryset = MagicMock()
    queryset.filter.return_value.exists.return_value = True

    with patch(
        "pbn_import.management.commands.fix_pbn_import_oswiadczen_ksiazki."
        "Wydawnictwo_Zwarte.objects"
    ) as objects:
        objects.exclude.return_value = queryset

        assert command._get_books_queryset("pub-1") == queryset.filter.return_value

    objects.exclude.assert_called_once_with(pbn_uid_id=None)
    queryset.filter.assert_called_once_with(pbn_uid_id="pub-1")


def test_book_statement_type_get_books_queryset_rejects_missing_publication():
    command = make_command(BookStatementTypeCommand)
    queryset = MagicMock()
    queryset.filter.return_value.exists.return_value = False

    with patch(
        "pbn_import.management.commands.fix_pbn_import_oswiadczen_ksiazki."
        "Wydawnictwo_Zwarte.objects"
    ) as objects:
        objects.exclude.return_value = queryset

        with pytest.raises(CommandError, match="Nie znaleziono publikacji"):
            command._get_books_queryset("missing")


def test_book_statement_type_update_counters():
    command = make_command(BookStatementTypeCommand)
    counters = {"fixed": 0, "no_wa": 0, "matching": 0, "to_integrate": []}
    statement = object()

    command._update_counters("fixed", counters, statement, integruj_dyscypliny=True)
    command._update_counters("no_wa", counters, statement, integruj_dyscypliny=True)
    command._update_counters("matching", counters, statement, integruj_dyscypliny=True)

    assert counters == {
        "fixed": 1,
        "no_wa": 1,
        "matching": 1,
        "to_integrate": [statement],
    }


def test_book_statement_type_find_author_record_branches():
    command = make_command(BookStatementTypeCommand)

    class DoesNotExist(Exception):
        pass

    class MultipleObjectsReturned(Exception):
        pass

    manager_model = SimpleNamespace(
        DoesNotExist=DoesNotExist,
        MultipleObjectsReturned=MultipleObjectsReturned,
    )
    manager = MagicMock(model=manager_model)
    book = SimpleNamespace(
        autorzy_set=manager,
        tytul_oryginalny="Book title",
    )
    expected_typ = SimpleNamespace(nazwa="redaktor")

    manager.get.return_value = "wa"
    assert command._find_autor_record(book, "autor", expected_typ, verbose=False) == (
        "wa",
        None,
    )

    manager.reset_mock()
    manager.get.side_effect = DoesNotExist
    assert command._find_autor_record(book, "autor", expected_typ, verbose=True) == (
        None,
        "no_wa",
    )

    manager.reset_mock()
    manager.get.side_effect = [MultipleObjectsReturned, "matching-wa"]
    assert command._find_autor_record(book, "autor", expected_typ, verbose=False) == (
        None,
        "matching",
    )

    fallback_wa = object()
    manager.reset_mock()
    manager.get.side_effect = [MultipleObjectsReturned, DoesNotExist]
    manager.filter.return_value.first.return_value = fallback_wa
    assert command._find_autor_record(book, "autor", expected_typ, verbose=False) == (
        fallback_wa,
        None,
    )


def test_book_statement_type_process_single_statement_updates_mismatched_type():
    command = make_command(BookStatementTypeCommand)
    typ_autor = SimpleNamespace(nazwa="autor")
    typ_redaktor = SimpleNamespace(nazwa="redaktor")
    wa = SimpleNamespace(
        typ_odpowiedzialnosci=typ_autor,
        save=MagicMock(),
    )
    book = SimpleNamespace(tytul_oryginalny="Book title")
    statement = SimpleNamespace(
        type="EDITOR",
        get_bpp_autor=MagicMock(return_value="BPP author"),
    )

    with patch.object(command, "_find_autor_record", return_value=(wa, None)):
        result = command._process_single_statement(
            book,
            statement,
            typ_autor,
            typ_redaktor,
            dry_run=False,
            verbose=True,
        )

    assert result == "fixed"
    assert wa.typ_odpowiedzialnosci is typ_redaktor
    wa.save.assert_called_once_with(update_fields=["typ_odpowiedzialnosci"])


def test_book_statement_type_process_single_statement_dry_run_does_not_save():
    command = make_command(BookStatementTypeCommand)
    typ_autor = SimpleNamespace(nazwa="autor")
    typ_redaktor = SimpleNamespace(nazwa="redaktor")
    wa = SimpleNamespace(
        typ_odpowiedzialnosci=typ_autor,
        save=MagicMock(),
    )
    book = SimpleNamespace(tytul_oryginalny="Book title")
    statement = SimpleNamespace(
        type="EDITOR",
        get_bpp_autor=MagicMock(return_value="BPP author"),
    )

    with patch.object(command, "_find_autor_record", return_value=(wa, None)):
        result = command._process_single_statement(
            book,
            statement,
            typ_autor,
            typ_redaktor,
            dry_run=True,
            verbose=False,
        )

    assert result == "fixed"
    assert wa.typ_odpowiedzialnosci is typ_autor
    wa.save.assert_not_called()


def test_book_statement_type_process_single_statement_matching_and_missing_author():
    command = make_command(BookStatementTypeCommand)
    typ_autor = SimpleNamespace(nazwa="autor")
    typ_redaktor = SimpleNamespace(nazwa="redaktor")
    book = SimpleNamespace(tytul_oryginalny="Book title")

    missing_author = SimpleNamespace(
        type="AUTHOR",
        personId="person-1",
        get_bpp_autor=MagicMock(return_value=None),
    )
    assert (
        command._process_single_statement(
            book,
            missing_author,
            typ_autor,
            typ_redaktor,
            dry_run=False,
            verbose=True,
        )
        == "no_wa"
    )

    matching_wa = SimpleNamespace(typ_odpowiedzialnosci=typ_autor)
    matching_statement = SimpleNamespace(
        type="AUTHOR",
        get_bpp_autor=MagicMock(return_value="BPP author"),
    )
    with patch.object(command, "_find_autor_record", return_value=(matching_wa, None)):
        assert (
            command._process_single_statement(
                book,
                matching_statement,
                typ_autor,
                typ_redaktor,
                dry_run=False,
                verbose=False,
            )
            == "matching"
        )


def test_book_statement_type_integrate_disciplines_reports_verbose_errors():
    command = make_command(BookStatementTypeCommand)
    statement = SimpleNamespace(publicationId="pub-1")

    with patch(
        "pbn_integrator.utils.statements."
        "integruj_oswiadczenia_z_instytucji_pojedyncza_praca",
        side_effect=RuntimeError("cannot integrate"),
    ) as integrate:
        with patch("bpp.models.Uczelnia.objects") as uczelnie:
            uczelnie.get.return_value = SimpleNamespace(domyslna_jednostka="unit")

            command._integrate_disciplines([statement], verbose=True)

    integrate.assert_called_once_with(
        statement,
        set(),
        set(),
        default_jednostka="unit",
    )
    output = command.stdout._out.getvalue()
    assert "Błąd integracji: pub-1" in output
    assert "Zintegrowano dyscypliny dla 1 rekordów" in output
