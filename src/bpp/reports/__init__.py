"""W tym pakciecie bpp.reports znajdują się raporty, które generowane są
za pomocą celery.
"""

import re

from celeryui.registry import registerAdapter

# Bo padną importy reports/__init__.py w chwili importowania formularzy

numery_stron_regex = re.compile(
    ".*((s|str)\\.\\s*(?P<strony>((\\w+)\\-(\\w+)|(\\w+)))).*"
)


def wytnij_numery_stron(s):
    """Wycina numery stron z pola szczegóły"""
    if s is None:
        return
    m = numery_stron_regex.match(s)
    if m is not None:
        return m.group("strony")


tomy_regex = re.compile(".*((vol\\.|tom|t\\.) (?P<tom>\\d+)).*")


def wytnij_tom(s):
    """
    Wycina tom po regexpie:
     * tom X
     * t. X
     * vol. X

    :param s: string
    :type s: str
    :return:
    :rtype: str
    """
    if s is None:
        return
    m = tomy_regex.match(s)
    if m:
        return m.group("tom")


def wytnij_zbedne_informacje_ze_zrodla(z):

    if z.startswith("W: "):
        z = z[3:]

    def splituj(v, co):
        if v.find(co):
            v = v.split(co)[0]
        return v

    for elem in [
        "Pod red. ",
        " Ed. ",
        "Red. ",
        "Pod. red. ",
        " Red. nauk. ",
        "Red. nauk. ",
        "Sci. ed. ",
        " Eds. ",
        "[Ed. by]",
        "Praca zbior.",
        "[Ed.]",
        "Sci. eds.",
        "Pr. zbior.",
        "Praca zbiorowa pod",
        "Aut.",
        "[Red.]",
        "Sci.ed.",
        "Praca zbiorowa",
        ": praca zbiorowa",
        "Ed.",
        "Edited by",
        "Wyd.",
        ": praca zbiorowa",
        " : [księga dedykowana",
    ]:
        z = splituj(z, elem)

    return z.strip()


# -*- encoding: utf-8 -*-


def slugify(title):
    return title.lower().replace(" ", "-")


import logging

logger = logging.getLogger(__name__)


def addToRegistry(klass):
    logger.info(f"rejestruje {klass.slug!r} jako {klass!r}")
    registerAdapter(klass.slug, klass)


# Poniższy import jest KONIECZNY żeby adaptery do registry się
# prawidłowo zassały (tasks.py importuje tylko toplevel-module)
