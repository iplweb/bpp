from django.core.urlresolvers import reverse


def test_wybor(preauth_webtest_app, wydzial):
    page = preauth_webtest_app.get(reverse('eksport_pbn:wybor_wydzialu'))
    assert '2013' in page.content


#def test_generuj(preauth_webtest_app, wydzial):
#    page = preauth_webtest_app.get(reverse('eksport_pbn:generuj', args=(wydzial.pk, 2013)))
#    assert page.status_code == 200
