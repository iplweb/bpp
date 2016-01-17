# -*- encoding: utf-8 -*-

from zope.component import getGlobalSiteManager
from celeryui.interfaces import IReport, IWebTask, IReportMaker

_REGISTRY = {}


class ReportAdapter:
    def __init__(self, original):
        self.original = original


def registerAdapter(function, klass):
    """This registers an adapter for reports with .function attribute
    to a given class."""
    _REGISTRY[function] = klass


def reportAdapter(original, *arg, **kw):
    return _REGISTRY.get(original.function)(original)


getGlobalSiteManager().registerAdapter(reportAdapter, [IReport], IWebTask)
getGlobalSiteManager().registerAdapter(reportAdapter, [IReport], IReportMaker)


