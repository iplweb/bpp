# -*- encoding: utf-8 -*-


def test_autor_eksport_pbn_serialize(autor_jan_kowalski):
    autor_jan_kowalski.pbn_id = 31337
    autor_jan_kowalski.save()

    ret = autor_jan_kowalski.eksport_pbn_serializuj()
    assert len(ret.findall("system-identifier")) == 2
