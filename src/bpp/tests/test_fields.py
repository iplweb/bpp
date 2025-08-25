from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from bpp.fields import CommaDecimalField


def test_fields_CommaDecimalField_accepts_decimal_with_period():
    """Test that field accepts decimal with period separator"""
    field = CommaDecimalField(max_digits=10, decimal_places=2)
    result = field.to_python("10.50")
    assert result == Decimal("10.50")


def test_fields_CommaDecimalField_accepts_decimal_with_comma():
    """Test that field accepts decimal with comma separator"""
    field = CommaDecimalField(max_digits=10, decimal_places=2)
    result = field.to_python("10,50")
    assert result == Decimal("10.50")


def test_fields_CommaDecimalField_period_and_comma_produce_same_result():
    """Test that period and comma separators produce identical results"""
    field = CommaDecimalField(max_digits=10, decimal_places=2)
    result_period = field.to_python("10.50")
    result_comma = field.to_python("10,50")
    assert result_period == result_comma


def test_fields_CommaDecimalField_accepts_integer_as_string():
    """Test that field accepts integer values as strings"""
    field = CommaDecimalField(max_digits=10, decimal_places=2)
    result = field.to_python("10")
    assert result == Decimal("10")


def test_fields_CommaDecimalField_accepts_decimal_object():
    """Test that field accepts Decimal objects directly"""
    field = CommaDecimalField(max_digits=10, decimal_places=2)
    decimal_value = Decimal("10.50")
    result = field.to_python(decimal_value)
    assert result == decimal_value


def test_fields_CommaDecimalField_accepts_float():
    """Test that field accepts float values"""
    field = CommaDecimalField(max_digits=10, decimal_places=2)
    result = field.to_python(10.50)
    assert result == Decimal("10.50")


def test_fields_CommaDecimalField_handles_none_value():
    """Test that field handles None values"""
    field = CommaDecimalField(max_digits=10, decimal_places=2)
    result = field.to_python(None)
    assert result is None


def test_fields_CommaDecimalField_handles_empty_string():
    """Test that field handles empty strings"""
    field = CommaDecimalField(max_digits=10, decimal_places=2)
    result = field.to_python("")
    assert result is None


def test_fields_CommaDecimalField_raises_validation_error_for_invalid_input():
    """Test that field raises ValidationError for invalid input"""
    field = CommaDecimalField(max_digits=10, decimal_places=2)
    with pytest.raises(ValidationError):
        field.to_python("invalid")


def test_fields_CommaDecimalField_raises_validation_error_for_multiple_separators():
    """Test that field raises ValidationError for multiple separators"""
    field = CommaDecimalField(max_digits=10, decimal_places=2)
    with pytest.raises(ValidationError):
        field.to_python("10.5,2")


def test_fields_CommaDecimalField_complex_decimal_with_comma():
    """Test complex decimal numbers with comma separator"""
    field = CommaDecimalField(max_digits=10, decimal_places=2)
    result = field.to_python("1234,56")
    assert result == Decimal("1234.56")


def test_fields_CommaDecimalField_complex_decimal_with_period():
    """Test complex decimal numbers with period separator"""
    field = CommaDecimalField(max_digits=10, decimal_places=2)
    result = field.to_python("1234.56")
    assert result == Decimal("1234.56")


def test_fields_CommaDecimalField_negative_decimal_with_comma():
    """Test negative decimal numbers with comma separator"""
    field = CommaDecimalField(max_digits=10, decimal_places=2)
    result = field.to_python("-10,50")
    assert result == Decimal("-10.50")


def test_fields_CommaDecimalField_negative_decimal_with_period():
    """Test negative decimal numbers with period separator"""
    field = CommaDecimalField(max_digits=10, decimal_places=2)
    result = field.to_python("-10.50")
    assert result == Decimal("-10.50")
