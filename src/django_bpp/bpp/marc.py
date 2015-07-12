# -*- encoding: utf-8 -*-

from pymarc import Record, Field
from bpp.models.system import Jezyk


def to_marc(orig):
    # TODO: obsługa formatu jest niekompletna, możnaby więcej pól eksportować...
    # OBECNIE NIEUŻYWANY
    record = Record()
    #
    # Autorzy - tag 100
    #

    if hasattr(orig, 'autor'):
        autorzy = [orig.autor,]
    else:
        autorzy = orig.autorzy.all()

    for autor in autorzy[:1]:
        subfields = ['a', u"%s, %s" % (autor.nazwisko, autor.imiona),]
        if autor.tytul != None:
            subfields.append('c')
            subfields.append(autor.tytul.nazwa)

        record.add_field(
            Field(
                tag='100', # autor
                indicators=['1', '@'], # imie, nazwisko
                subfields=subfields))

    for autor in autorzy[1:]:
        subfields = ['a', u"%s, %s" % (autor.nazwisko, autor.imiona),]
        record.add_field(
            Field(
                tag='700', # autor
                indicators=['1', '@'], # imie, nazwisko
                subfields=subfields))


    #
    # Tytuł - tag 245
    #


    # TODO: znaki przy szeregowaniu
    record.add_field(
        Field(
            tag='245',
            indicators=['0', '0'],
            subfields=[
                'a', orig.tytul_oryginalny
            ]
        )
    )

    jezyk = None
    if hasattr(orig, 'jezyk'):
        if orig.jezyk:
            jezyk = orig.jezyk.skrot
    else:
        jezyk = Jezyk.objects.get(nazwa='polski').skrot

    #
    # Tytuł dodatkowy - tag 730
    #

    if hasattr(orig, 'tytul'):
        if orig.tytul:
            subfields = [
                'a', orig.tytul
            ]

            if hasattr(orig, 'rok'):
                subfields.append('f')
                subfields.append(str(orig.rok))

            if jezyk is not None:
                subfields.append('l')
                subfields.append(jezyk)

            record.add_field(
                Field(
                    tag='730',
                    # TODO: znaki przy szeregowaniu
                    indicators=['0', '0'],
                    subfields=subfields))

    #
    # ISSN - tag 022
    #

    if hasattr(orig, 'issn'):
        if orig.issn:
            record.add_field(
                Field(
                    tag='022',
                    indicators=['#', '#'],
                    subfields=[
                        'a', orig.issn
                    ]
                )
            )

    #
    # ISBN - tag 020
    #

    if hasattr(orig, 'isbn'):
        if orig.isbn:
            record.add_field(
                Field(
                    tag='020',
                    indicators=['#', '#'],
                    subfields=[
                        'a', orig.isbn.replace("-", "")
                    ]
                )
            )

    return record