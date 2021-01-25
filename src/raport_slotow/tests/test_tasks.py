from raport_slotow.tasks.uczelnia import wygeneruj_raport_slotow_uczelnia


def test_wygeneruj_raport_slotow_uczelnia(raport_slotow_uczelnia):
    rsu = raport_slotow_uczelnia
    rsu.create_report = lambda: True
    wygeneruj_raport_slotow_uczelnia.delay(rsu.pk)
    rsu.refresh_from_db()
    assert rsu.finished_successfully
