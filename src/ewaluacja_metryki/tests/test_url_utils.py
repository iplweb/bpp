import pytest
from django.http import HttpRequest, QueryDict
from django.template import Context, Template


@pytest.mark.django_db
def test_update_query_param_removes_page_on_sort_change():
    """Test that changing sort parameter removes page parameter"""
    request = HttpRequest()
    request.GET = QueryDict("sort=autor__nazwisko&page=2&nazwisko=test")

    template_str = """
    {% load url_utils %}
    {% update_query_param request 'sort' '-autor__nazwisko' %}
    """

    template = Template(template_str)
    context = Context({"request": request})
    result = template.render(context).strip()

    # Should contain new sort value
    assert "sort=-autor__nazwisko" in result
    # Should preserve filter
    assert "nazwisko=test" in result
    # Should NOT contain page parameter (removed when sort changes)
    assert "page=" not in result


@pytest.mark.django_db
def test_preserve_filters_keeps_all_params():
    """Test that preserve_filters keeps all parameters when updating page"""
    request = HttpRequest()
    request.GET = QueryDict(
        "sort=-srednia_za_slot_nazbierana&nazwisko=test&jednostka=5"
    )

    template_str = """
    {% load url_utils %}
    {% preserve_filters request page=3 %}
    """

    template = Template(template_str)
    context = Context({"request": request})
    result = template.render(context).strip()

    # Should contain page
    assert "page=3" in result
    # Should preserve sort
    assert "sort=-srednia_za_slot_nazbierana" in result
    # Should preserve filters
    assert "nazwisko=test" in result
    assert "jednostka=5" in result


@pytest.mark.django_db
def test_update_query_param_toggle_sort_direction():
    """Test toggling sort direction preserves other params but removes page"""
    request = HttpRequest()
    request.GET = QueryDict("sort=-procent_wykorzystania_slotow&dyscyplina=3&page=5")

    template_str = """
    {% load url_utils %}
    {% update_query_param request 'sort' 'procent_wykorzystania_slotow' %}
    """

    template = Template(template_str)
    context = Context({"request": request})
    result = template.render(context).strip()

    # Should have toggled sort direction
    assert "sort=procent_wykorzystania_slotow" in result
    assert "sort=-procent_wykorzystania_slotow" not in result
    # Should preserve filter
    assert "dyscyplina=3" in result
    # Should remove page
    assert "page=" not in result


@pytest.mark.django_db
def test_build_query_string_with_multiple_updates():
    """Test build_query_string with multiple parameter updates"""
    request = HttpRequest()
    request.GET = QueryDict("sort=autor__nazwisko&page=2&nazwisko=test")

    template_str = """
    {% load url_utils %}
    {% build_query_string request sort='-autor__nazwisko' jednostka='10' page=None %}
    """

    template = Template(template_str)
    context = Context({"request": request})
    result = template.render(context).strip()

    # Should update sort
    assert "sort=-autor__nazwisko" in result
    # Should add new parameter
    assert "jednostka=10" in result
    # Should preserve existing filter
    assert "nazwisko=test" in result
    # Should remove page (explicitly set to None)
    assert "page=" not in result
