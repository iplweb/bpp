from django import forms


class ORCIDField(forms.CharField):
    def __init__(self, *args, **kwargs):
        kwargs["max_length"] = 19
        kwargs["min_length"] = 19
        super().__init__(*args, **kwargs)
