"""Concrete view subclasses for DemoOp — used only in the test suite."""
from django import forms

from live_operations.views import (
    CancelView,
    CreateLiveOperationView,
    LiveOperationListView,
    LiveOperationView,
    RestartView,
)
from tests.models import DemoOp


class DemoOpForm(forms.ModelForm):
    class Meta:
        model = DemoOp
        fields: list = []


class CreateDemoOpView(CreateLiveOperationView):
    model = DemoOp
    form_class = DemoOpForm


class LiveDemoOpView(LiveOperationView):
    model = DemoOp


class ListDemoOpView(LiveOperationListView):
    model = DemoOp


class CancelDemoOpView(CancelView):
    model = DemoOp


class RestartDemoOpView(RestartView):
    model = DemoOp
