from zglos_publikacje.models import Obslugujacy_Zgloszenia_Wydzialow


def test_Obslugujacy_Zgloszenia_WydzialowManager_emaile_dla_wydzialu(
    wydzial, normal_django_user
):
    normal_django_user.email = "foo@bar.pl"
    normal_django_user.save()

    assert Obslugujacy_Zgloszenia_Wydzialow.objects.emaile_dla_wydzialu(wydzial) is None

    Obslugujacy_Zgloszenia_Wydzialow.objects.create(
        user=normal_django_user, wydzial=wydzial
    )
    assert Obslugujacy_Zgloszenia_Wydzialow.objects.emaile_dla_wydzialu(wydzial) == [
        normal_django_user.email
    ]
