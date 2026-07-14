import pytest

from django_pbn_client.pages import (
    ThreadedModelSaver,
    ThreadedMongoDBSaver,
    ThreadedPageGetter,
    download_pages,
    simple_page_getter,
)


def test_threaded_model_saver_uses_injected_model_and_save_function():
    calls = []
    model_class = object()

    class Saver(ThreadedModelSaver):
        save_function = staticmethod(
            lambda element, model: calls.append((element, model))
        )

    saver = Saver(model_class=model_class)
    saver.process_element({"mongoId": "one"})

    assert calls == [({"mongoId": "one"}, model_class)]
    assert ThreadedMongoDBSaver is ThreadedModelSaver


def test_download_pages_processes_each_page_with_host_progress():
    processed = []
    progress_calls = []

    class Data:
        total_pages = 3

        def fetch_page(self, page_number):
            return [page_number * 2, page_number * 2 + 1]

    class Getter(ThreadedPageGetter):
        def process_element(self, element):
            processed.append((self.client, element))

    def progress(pages, total, label):
        progress_calls.append((total, label))
        return pages

    client = object()
    download_pages(
        client,
        Data(),
        getter_class=Getter,
        workers=2,
        label="Pages",
        progress=progress,
    )

    assert progress_calls == [(3, "Pages")]
    assert sorted(processed, key=lambda item: item[1]) == [
        (client, 0),
        (client, 1),
        (client, 2),
        (client, 3),
        (client, 4),
        (client, 5),
    ]


def test_download_pages_rejects_unknown_concurrency_method():
    class Data:
        total_pages = 0

    with pytest.raises(ValueError, match="greenlets"):
        download_pages(None, Data(), method="greenlets")


@pytest.mark.django_db
def test_process_workers_use_their_initialized_getter():
    class Data:
        total_pages = 2

        def fetch_page(self, _page_number):
            return []

    download_pages(None, Data(), method="processes", workers=1)


def test_simple_page_getter_yields_each_page_in_order():
    class Data:
        total_pages = 3

        def fetch_page(self, page_number):
            return [f"page-{page_number}"]

    assert list(simple_page_getter(None, Data())) == [
        ["page-0"],
        ["page-1"],
        ["page-2"],
    ]
