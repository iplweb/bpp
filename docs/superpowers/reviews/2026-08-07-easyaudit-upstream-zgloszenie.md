# Zgłoszenie do upstreamu `django-easy-audit` — gotowy tekst

**Gdzie wkleić:** komentarz do istniejącego
[issue #175](https://github.com/soynatan/django-easy-audit/issues/175)
(otwarte od 2021-02, dokładnie ten problem). Nowego issue NIE zakładamy —
byłby piątym równoległym wątkiem o tej samej sprawie.

**Dlaczego warto mimo czterech nieudanych prób:** poprzednie zgłoszenia
(#168, #176, #318, #342) nie zawierały informacji, która jest tu kluczowa —
że obejście sugerowane przez maintainera jest **nieosiągalne**. To jedyna
nowa przesłanka, jaką wnosimy do dyskusji.

**Po scaleniu:** skasować `src/bpp/easyaudit_shim.py` + wywołanie
`zainstaluj()` w `BppConfig.ready()` + `test_easyaudit_shim.py`. Przypomni
o tym test `test_upstream_nadal_ma_blad_czyli_shim_jest_potrzebny`, który
wtedy zacznie padać.

---

## Treść komentarza (EN)

> ### The documented workaround for this issue is unreachable
>
> We hit this on a Django 5.2 project with soft-deletable models
> (`django-soft-delete`), on `django-easy-audit==1.3.9`. I want to add one
> piece of information that I don't think has been stated in this thread or
> in the related PRs (#168, #176, #318, #342), because I believe it explains
> why the fix keeps stalling.
>
> In #168 the suggestion was to handle this via
> `DJANGO_EASY_AUDIT_CRUD_DIFFERENCE_CALLBACKS`, letting the application
> decide whether to create the `CRUDEvent`.
>
> **That workaround cannot work for this bug.** The exception is raised
> *before* the callbacks are ever consulted. In `signals/model_signals.py`
> (1.3.9):
>
> ```python
> # line 102 — raises DoesNotExist
> old_model = sender.objects.get(pk=instance.pk)
> delta = model_delta(old_model, instance)
> ...
> # line 113 — callbacks are only reached here
> create_crud_event = call_callbacks(...)
> ```
>
> So an application cannot opt out of the failing lookup: by the time it is
> asked, the lookup has already thrown. With
> `DJANGO_EASY_AUDIT_PROPAGATE_EXCEPTIONS = True` (which we need, so that
> audit failures are not silently swallowed) the exception then propagates
> and aborts the user's write.
>
> ### Minimal reproduction
>
> ```python
> class Article(SoftDeleteModel):        # objects filters deleted_at IS NULL
>     title = models.CharField(max_length=100)
>
> # settings.py
> DJANGO_EASY_AUDIT_REGISTERED_CLASSES = ["myapp.Article"]
> DJANGO_EASY_AUDIT_PROPAGATE_EXCEPTIONS = True
>
> a = Article.objects.create(title="x")
> a.delete()                              # soft delete
> Article.global_objects.get(pk=a.pk).restore()
> # -> Article.DoesNotExist: Article matching query does not exist
> ```
>
> The row exists the whole time; it is merely hidden from `objects`. Any
> `save()` on a currently-hidden row fails the same way — `restore()` is
> just the case that always hits it, because the row is by definition still
> flagged as deleted at `pre_save` time.
>
> ### Suggested fix
>
> One line:
>
> ```diff
> - old_model = sender.objects.get(pk=instance.pk)
> + old_model = sender._base_manager.get(pk=instance.pk)
> ```
>
> `_base_manager` rather than `_default_manager`, for the reason
> @sgordon16 already gave in this thread: the *default* manager may itself
> filter, so it does not remove the failure mode. `_base_manager` is the
> one Django documents for exactly this purpose — retrieving related/
> internal objects — and
> [the docs state it must not filter out any results](https://docs.djangoproject.com/en/5.2/topics/db/managers/#django.db.models.Manager.base_manager_name).
>
> Worth noting: when a model does not set `Meta.base_manager_name`, Django
> creates a plain unfiltered `Manager` for `_base_manager` automatically.
> So this change is a no-op for every project that does not deliberately
> override it, and it does not require model authors to configure anything.
> We verified this on our models — `_base_manager` sees soft-deleted rows,
> `objects` does not.
>
> This is a semantic correction, not a workaround: `pre_save` wants "the row
> currently stored under this pk", which is precisely what `_base_manager`
> means, and is not what `objects` means for any project with a filtering
> default manager.
>
> ### Scope
>
> Grepping 1.3.9, this is the **only** place in the package where an audited
> model's manager is used to fetch an instance; every other `.objects` usage
> is on `CRUDEvent`, `LoginEvent`, `ContentType` or `User`. So the change is
> contained.
>
> We are currently carrying this as a local patch that replaces the
> `pre_save` receiver via its `dispatch_uid`. Happy to open a PR (with a
> regression test using a filtering default manager) if that would help move
> this along — just let me know whether you would prefer it on top of #318
> or as a fresh branch.
