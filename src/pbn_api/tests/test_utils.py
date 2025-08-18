from pbn_api.utils import rename_dict_key


def test_rename_dict_key_simple():
    d = {"mniswId": 123}
    res = rename_dict_key(d, "mniswId", "ministryId")

    assert "mniswId" in d
    assert "ministryId" not in d

    assert "ministryId" in res
    assert "mniswId" not in res


def test_rename_dict_key_nested():
    d = {"test": {"mniswId": 123}}
    res = rename_dict_key(d, "mniswId", "ministryId")

    assert "mniswId" in d["test"]
    assert "ministryId" not in d["test"]

    assert "ministryId" in res["test"]
    assert "mniswId" not in res["test"]


def test_rename_dict_key_nested_in_list():
    d = [{"test": [{"mniswId": 123}]}]
    res = rename_dict_key(d, "mniswId", "ministryId")

    assert "mniswId" in d[0]["test"][0]
    assert "ministryId" not in d[0]["test"][0]

    assert "ministryId" in res[0]["test"][0]
    assert "mniswId" not in res[0]["test"][0]


def test_rename_dict_key_real():
    d = {
        "editors": [{"givenNames": "Ma\u0142gorzata Anna", "lastName": "Test"}],
        "isbn": "9788367881944",
        "mainLanguage": "pol",
        "publicUri": "https://test",
        "publicationPlace": "Lublin",
        "publisher": {
            "mniswId": 85900,
            "name": "Wydawnictwo Naukowe TYGIEL Sp. z o. o.",
            "objectId": "21234",
        },
        "title": "Test",
        "translation": False,
        "type": "EDITED_BOOK",
        "year": 2025,
    }

    res = rename_dict_key(d, "mniswId", "ministryId")

    assert "mniswId" in d["publisher"]
    assert "ministryId" not in d["publisher"]

    assert "ministryId" in res["publisher"]
    assert "mniswId" not in res["publisher"]


def test_rename_dict_key_real_list():
    d = [
        {
            "editors": [{"givenNames": "Ma\u0142gorzata Anna", "lastName": "Test"}],
            "isbn": "Test",
            "mainLanguage": "pol",
            "publicUri": "Test",
            "publicationPlace": "Lublin",
            "publisher": [
                {
                    "mniswId": 85900,
                    "name": "Wydawnictwo Naukowe TYGIEL Sp. z o. o.",
                    "objectId": "Test",
                }
            ],
            "title": "Test",
            "translation": False,
            "type": "EDITED_BOOK",
            "year": 2025,
        }
    ]

    res = rename_dict_key(d, "mniswId", "ministryId")

    assert "mniswId" in d[0]["publisher"][0]
    assert "ministryId" not in d[0]["publisher"][0]

    assert "ministryId" in res[0]["publisher"][0]
    assert "mniswId" not in res[0]["publisher"][0]
