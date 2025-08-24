from unittest.mock import patch

from bpp.export.issn import generate_issn_xlsx_workbook


def test_generate_issn_xlsx_workbook_random_rows_per_column():
    """Test that generate_issn_xlsx_workbook uses random rows per column between 450-595"""
    # Create test data with enough ISSNs to fill multiple columns
    test_issns = [f"1234-567{i:01d}" for i in range(2000)]

    # Mock random.randint to return predictable values for testing
    with patch("bpp.export.issn.random.randint", side_effect=[500, 450, 595, 475]):
        wb = generate_issn_xlsx_workbook(test_issns)
        ws = wb.active

        # Check that data is distributed according to our mocked random values
        # Column 1 should have 500 rows
        assert ws.cell(row=500, column=1).value is not None
        assert ws.cell(row=501, column=1).value is None

        # Column 2 should have 450 rows (starting from item 501)
        assert ws.cell(row=450, column=2).value is not None
        assert ws.cell(row=451, column=2).value is None

        # Column 3 should have 595 rows (starting from item 951)
        assert ws.cell(row=595, column=3).value is not None
        assert ws.cell(row=596, column=3).value is None


def test_generate_issn_xlsx_workbook_with_small_dataset():
    """Test that function works correctly with a small dataset that fits in one column"""
    test_issns = ["1234-5678", "2345-6789", "3456-7890"]

    wb = generate_issn_xlsx_workbook(test_issns)
    ws = wb.active

    # All ISSNs should be in column 1
    assert ws.cell(row=1, column=1).value == "1234-5678"
    assert ws.cell(row=2, column=1).value == "2345-6789"
    assert ws.cell(row=3, column=1).value == "3456-7890"
    assert ws.cell(row=4, column=1).value is None
    assert ws.cell(row=1, column=2).value is None


def test_generate_issn_xlsx_workbook_empty_list():
    """Test that function handles empty ISSN list correctly"""
    wb = generate_issn_xlsx_workbook([])
    ws = wb.active

    # Should have no data
    assert ws.cell(row=1, column=1).value is None


def test_generate_issn_xlsx_workbook_random_range():
    """Test that random values are actually called with correct range"""
    test_issns = [f"1234-567{i:01d}" for i in range(1000)]

    with patch("bpp.export.issn.random.randint") as mock_randint:
        mock_randint.return_value = 500
        generate_issn_xlsx_workbook(test_issns)

        # Verify that random.randint was called with the correct range (450, 595)
        mock_randint.assert_called_with(450, 595)
        # Should be called at least twice (once for first column, once for second)
        assert mock_randint.call_count >= 2
