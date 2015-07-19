# -*- encoding: utf-8 -*-

from django.test import TestCase, TransactionTestCase
from django.test.client import Client, RequestFactory
from django.contrib import auth

User = auth.get_user_model()


class UserRequestFactory(RequestFactory):
    def __init__(self, user, *args, **kw):
        self.user = user
        super(UserRequestFactory, self).__init__(*args, **kw)

    def get(self, *args, **kw):
        req = super(UserRequestFactory, self).get(*args, **kw)
        req.user = self.user
        return req

    def post(self, *args, **kw):
        req = super(UserRequestFactory, self).post(*args, **kw)
        req.user = self.user
        return req


class WebTestCaseMixin:
    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()


class WebTestCase(WebTestCaseMixin, TestCase):
    pass


class WebTransactionTestCase(WebTestCaseMixin, TransactionTestCase):
    pass


class UserTestCaseMixin:
    USERNAME = "user"
    PASSWORD = "foo"
    EMAIL = "foo@bar.pl"
    create = User.objects.create_user

    def setUp(self):
        self.user = self.create(
            username=self.USERNAME, password=self.PASSWORD,
            email=self.EMAIL)
        res = self.client.login(username=self.USERNAME, password=self.PASSWORD)
        if res is not True:
            raise Exception("Cannot login")

        self.factory = UserRequestFactory(self.user)


class UserTestCase(UserTestCaseMixin, WebTestCase):
    def setUp(self):
        WebTestCase.setUp(self)
        UserTestCaseMixin.setUp(self)
    pass


class UserTransactionTestCase(UserTestCaseMixin, WebTransactionTestCase):
    pass

class SuperuserTestCase(UserTestCase):
    create = User.objects.create_superuser
