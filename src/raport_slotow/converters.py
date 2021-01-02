from decimal import Decimal


class DecimalPathConverter:
    regex = "^(\d+(?:\.\d+)?)$"

    def to_python(self, value):
        # convert value to its corresponding python datatype
        return Decimal(value)

    def to_url(self, value):
        # convert the value to str data
        return str(value)
