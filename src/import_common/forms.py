import xlrd
from django.forms import DateField


class ExcelDateField(DateField):
    def to_python(self, value):
        if isinstance(value, float):
            return xlrd.xldate_as_datetime(value, 0).date()
        return super(ExcelDateField, self).to_python(value)
