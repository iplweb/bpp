from django.utils.safestring import mark_safe


def monkeypatched_results(cl):
    from django.contrib.admin.templatetags.admin_list import (
        ResultList,
        items_for_result,
    )

    if cl.formset:
        for res, form in zip(cl.result_list, cl.formset.forms):
            yield ResultList(form, items_for_result(cl, res, form))
    else:
        for res in cl.result_list:
            yield ResultList(
                None,
                [
                    mark_safe(x.replace(' nowrap"', '"'))
                    for x in items_for_result(cl, res, None)
                ],
            )


from django.contrib.admin.templatetags import admin_list

admin_list.results = monkeypatched_results
