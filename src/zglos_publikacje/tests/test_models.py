from zglos_publikacje.models import Obslugujacy_Zgloszenia_Wydzialow


def test_Obslugujacy_Zgloszenia_WydzialowManager_emaile_dla_obslugujacego(
    wydzial, normal_django_user
):
    # Faza B (#438) II-2: ``wydzial`` to teraz FK->Jednostka (korzeń drzewa,
    # węzeł-lustro dawnego Wydzialu).

    jednostka_root = wydzial

    normal_django_user.email = "foo@bar.pl"
    normal_django_user.save()

    manager = Obslugujacy_Zgloszenia_Wydzialow.objects
    assert manager.emaile_dla_obslugujacego(jednostka_root) is None

    Obslugujacy_Zgloszenia_Wydzialow.objects.create(
        user=normal_django_user, wydzial=jednostka_root
    )
    assert manager.emaile_dla_obslugujacego(jednostka_root) == [
        normal_django_user.email
    ]
