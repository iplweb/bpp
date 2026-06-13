# Performance review: database, static assets, background work

Date: 2026-06-13

Scope: static code review of serious performance opportunities in BPP. This
report focuses on database triggers and indexes, JavaScript/static delivery,
background tasks, and larger architectural changes. It intentionally avoids
minor cleanup and style-only issues.

Methodology note: this is not a runtime profiling report. Priorities are based
on code-path shape, known write/read amplification, and the existing local
performance documentation. Each recommendation below should still be validated
against a production-like dump or production statistics before implementation.

## Executive priorities

1. Replace the row-level cache refresh trigger hot path with a durable,
   deduplicating refresh queue and batch drainers.
2. Add real normalized/trigram indexes for import, deduplication, Crossref,
   autocomplete, and source-mapping searches.
3. Split Celery workers by workload and stop using worker slots as pollers for
   child workflows.
4. Move appserver boot work and runtime asset compression to build/release
   jobs.
5. Split global frontend/admin assets and lazy-load third-party support and
   charting scripts.
6. Convert long-running evaluation and optimization flows into persistent
   state machines.

## Database triggers and indexes

### DB-1 [High] Row-level cache refresh still serializes heavy writes

Evidence:

- `src/bpp/migrations/0429_cache_trigger_v3.sql:38`
- `src/bpp/migrations/0429_cache_trigger_v3.sql:127`
- `src/bpp/migrations/0428_weighted_publication_fulltext.py:6`
- `src/bpp/management/commands/rebuild_search_index.py:68`

Why this matters:

`bpp_refresh_cache()` is still a `FOR EACH ROW` PL/Python trigger. For every
changed publication/author relation row it routes the event, computes target
materialized rows, takes an advisory transaction lock, and performs per-row
DELETE/UPSERT work. Version 3 removed important waste, but the architecture is
still row-driven. The migration comment for weighted fulltext search already
documents the practical failure mode: full-table updates can exhaust shared
memory and lock accounting when triggers and denorm subtransactions fire per
row.

The rebuild command works around this by disabling triggers and updating
`bpp_rekord_mat` directly. That is strong evidence that normal write paths are
still too expensive for bulk imports, mass denorm rebuilds, and schema changes
that touch many publication rows.

How I would fix it:

Create a small durable queue table, for example:

```sql
CREATE TABLE bpp_cache_refresh_queue (
    content_type_id integer NOT NULL,
    object_id integer NOT NULL,
    reason text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (content_type_id, object_id)
);
```

The trigger should only determine the affected `(content_type_id, object_id)`
pairs and insert them with `ON CONFLICT DO NOTHING`. A separate drainer should
fetch queued keys in batches, group by content type, and refresh
`bpp_rekord_mat`/`bpp_autorzy_mat` with set-based SQL. For high-value cases,
use statement-level triggers with transition tables to insert all changed keys
in one statement instead of one trigger call per row.

Keep the current row trigger as a compatibility fallback at first. Add a feature
flag or migration setting that lets the drainer path run side by side in staging
before making it the default.

How to verify:

- Benchmark bulk `UPDATE` and import-like writes on a production-like dump.
- Compare total trigger time, transaction duration, locks, and dead tuples.
- Verify that queue deduplication collapses repeated changes to the same
  publication into one refresh.
- Add correctness tests for insert, update, delete, author-through changes, and
  publication type-specific refreshes.

### DB-2 [High] Trigram searches compute normalized expressions at query time

Evidence:

- `src/import_common/core/publikacja.py:234`
- `src/import_common/core/normalize_db.py:12`
- `src/deduplikator_zrodel/utils.py:76`
- `src/crossref_bpp/utils.py:45`
- `src/bpp/views/autocomplete/base.py:26`
- `src/przemapuj_zrodla_pbn/views.py:95`

Why this matters:

Several import, deduplication, Crossref, autocomplete, and PBN source-mapping
paths compute expressions such as lowercased/replaced titles and then annotate
`TrigramSimilarity`. Queries that look like `similarity(expression, value)` and
then sort by score often cannot use ordinary btree indexes. Low thresholds such
as `0.05` make this even more expensive because many rows are eligible before
the final top-N sort.

These paths are important because they run during imports and interactive
search-like workflows, where latency and database load both matter.

How I would fix it:

Pick the canonical normalization rules for publications, sources, and authors.
Persist them either as generated columns or as ordinary columns maintained by
model save/import code. Then add `GIN` trigram indexes with `gin_trgm_ops` on
the exact normalized columns used by queries.

For query shape, avoid "compute similarity for the whole table, sort, limit".
Use an indexed prefilter first, for example PostgreSQL trigram `%` or
`__trigram_similar`, then compute similarity only for the candidate set and
sort the limited result. If the existing threshold must remain very low, use
additional predicates such as year, source type, first significant token, ISBN,
DOI, or author surname to keep the candidate set bounded.

How to verify:

- Add `EXPLAIN (ANALYZE, BUFFERS)` snapshots for representative import and
  autocomplete queries before and after.
- Track query latency for common and worst-case strings.
- Verify correctness against existing fuzzy-match fixtures, because trigram
  index usage can change candidate ordering near the threshold.

### DB-3 [High] Free-text fields use low-value btree indexes

Evidence:

- `src/bpp/models/abstract/naming.py:48`
- `src/bpp/models/zrodlo.py:136`
- `src/bpp/models/abstract/identifiers.py:40`
- `src/bpp/migrations/0422_drop_unused_cache_indexes.sql:1`

Why this matters:

Several `TextField` values have `db_index=True`. A btree index on long text is
only useful for exact equality and some prefix patterns. It does not help
trigram similarity, `icontains`, unaccented comparisons, or normalized matching.
The project already dropped unused cache-table btree text indexes in an earlier
migration, which suggests the same pattern should be audited on base tables.

Every unnecessary index makes writes slower and increases table bloat pressure.
This matters on publication/source tables because imports and denorm refreshes
are write-heavy.

How I would fix it:

Use production `pg_stat_user_indexes` to classify text indexes into:

- exact-match indexes that are genuinely used,
- prefix-search indexes that need `text_pattern_ops`,
- fuzzy-search indexes that should become trigram indexes,
- unused indexes to remove.

For fields used by fuzzy matching, replace plain btree indexes with functional
or generated-column trigram indexes. For fields that are unique or exact-match
identifiers, keep btree but make sure the stored form is canonical.

How to verify:

- Capture index usage from production before deleting anything.
- Apply index changes with concurrent SQL migrations where needed.
- Measure write amplification and index size reduction after removal.

### DB-4 [High] ISBN/ISSN matching needs canonical indexed values

Evidence:

- `src/import_common/core/normalize_db.py:66`
- `src/import_common/core/publikacja.py:160`
- `src/deduplikator_zrodel/utils.py:64`

Why this matters:

Import and source-deduplication code normalizes identifiers by lowercasing and
removing punctuation, but some lookups still rely on raw fields or regex-like
filters. Btree indexes on raw `isbn`, `e_isbn`, `issn`, or `e_issn` only help if
the stored value and lookup value have the same canonical shape. Regex and
expression filters usually bypass those indexes.

Identifier matching should be the fastest and most selective path in import and
deduplication workflows. If it is not indexed correctly, the system falls back
to fuzzy title/source matching more often.

How I would fix it:

Add canonical columns such as `isbn_norm`, `e_isbn_norm`, `issn_norm`, and
`e_issn_norm`, or add equivalent functional indexes if generated columns are
not desirable. Normalize by removing hyphens, spaces, and case differences.
Rewrite import and deduplication queries to use exact equality on normalized
values.

If schema changes are preferred over functional indexes, backfill values in a
separate migration and add constraints/tests that keep the canonical fields in
sync.

How to verify:

- Add tests where stored identifiers contain hyphens/spaces and imported values
  do not.
- Check `EXPLAIN` for exact index scans on normalized identifier columns.
- Compare dedup/import candidate counts before and after.

### DB-5 [Medium] Author import matching repeatedly normalizes names in SQL

Evidence:

- `src/import_common/core/autor.py:211`
- `src/import_common/core/autor.py:310`
- `src/bpp/models/autor.py:84`

Why this matters:

Author matching annotates `Lower(Unaccent(...))` for surname and first-name
fields. Raw btree indexes on `nazwisko` and `imiona` do not support these
expression filters. On a large author table, this can turn common import
operations into repeated scans or expensive function evaluation.

How I would fix it:

Add normalized author match columns or functional indexes:

- `lower(unaccent(nazwisko))`
- optionally `lower(unaccent(imiona))`
- optionally a first-initial or first-name-prefix helper if matching rules use
  initials often.

Then rewrite the author matching code to use the indexed expression or persisted
column directly. If generated columns cannot call `unaccent` safely in the
current PostgreSQL setup, use functional indexes and keep the expression exactly
identical to query code.

How to verify:

- Benchmark author import matching with common Polish diacritic cases.
- Add tests for accents, previous surnames, initials, and ambiguous authors.
- Confirm index usage with `EXPLAIN (ANALYZE, BUFFERS)`.

### DB-6 [High] PBN export queue lacks indexes matching worker selection

Evidence:

- `src/pbn_export_queue/models.py:74`
- `src/pbn_export_queue/tasks.py:85`
- `src/pbn_export_queue/tasks.py:203`
- `src/pbn_export_queue/tasks.py:219`

Why this matters:

The queue model has many single-column indexes, but workers query combinations
such as "not started, not finished, not excluded, not waiting for user
authorization, ordered by request time" or "started long ago, not finished".
Single-column indexes are a poor fit for these predicates. PostgreSQL may still
scan and filter many rows before finding the next work item.

Queue tables often look small until a retry storm, external API outage, or
stuck job creates thousands of rows. That is exactly when worker selection must
remain cheap.

How I would fix it:

Add partial composite indexes matching the queue states:

```sql
CREATE INDEX CONCURRENTLY pbn_export_open_requested_idx
ON pbn_export_queue_pbn_export_queue (zamowiono)
WHERE wysylke_podjeto IS NULL
  AND wysylke_zakonczono IS NULL
  AND wykluczone = false
  AND retry_after_user_authorised = false;

CREATE INDEX CONCURRENTLY pbn_export_stale_started_idx
ON pbn_export_queue_pbn_export_queue (wysylke_podjeto)
WHERE wysylke_zakonczono IS NULL
  AND wykluczone = false
  AND retry_after_user_authorised = false;
```

Also consider a partial uniqueness constraint for open work items by
`(content_type_id, object_id)` so duplicate queue entries are prevented by the
database, not only by application logic.

How to verify:

- Use `EXPLAIN` for the worker selection queries with realistic queue volume.
- Simulate many finished rows and many retry-blocked rows.
- Confirm the planner uses the partial indexes for the exact predicates.

### DB-7 [Medium] Source deduplication does per-candidate similarity SQL

Evidence:

- `src/deduplikator_zrodel/utils.py:168`
- `src/deduplikator_zrodel/utils.py:223`

Why this matters:

The source deduplication scoring path can run separate similarity queries for
individual candidates. This multiplies round trips and repeated SQL function
evaluation. If candidate lists grow, the scoring phase becomes O(N) database
queries instead of one indexed candidate query plus local scoring.

How I would fix it:

Build one candidate queryset that annotates all similarity values needed for
the score, including name and abbreviation similarity. Fetch the candidate rows
with those annotated floats and compute the final score in Python. If the
candidate list is already intentionally small, move all remaining string scoring
to Python and avoid extra SQL entirely.

How to verify:

- Add query-count tests around the deduplication scoring path.
- Benchmark candidate sets of 10, 100, and 1000 sources.
- Compare final candidate ordering with the current implementation.

### DB-8 [Medium] PBN import progress writes create unnecessary DB churn

Evidence:

- `src/pbn_import/utils/base.py:21`
- `src/pbn_import/utils/base.py:113`

Why this matters:

Progress updates save JSON state frequently and can perform multiple saves for
one logical update. During large imports this creates steady write traffic that
does not represent durable business data. It also increases row churn on
session/progress tables.

How I would fix it:

Combine progress field updates into a single `save(update_fields=[...])`.
Throttle persistence to a larger interval, for example 2-5 seconds, or only
persist when progress changes by a meaningful percentage. If live UI updates
need higher frequency, publish transient progress through Redis/channels and
persist periodic checkpoints to the database.

How to verify:

- Count SQL writes during a representative import before and after.
- Ensure UI progress still updates acceptably.
- Test crash recovery to make sure persisted checkpoints are frequent enough.

## JavaScript and static-file delivery

### JS-1 [High] Global public CSS bundle is too broad

Evidence:

- `src/django_bpp/templates/bare.html:43`

Why this matters:

The base template compresses and ships a broad CSS set to most public pages:
Foundation, jQuery UI, multiseek, session security, icons, datepicker, Select2,
cookielaw, DataTables, and application styles. Many pages need only a subset.
This increases transfer size, parse time, and render-blocking CSS cost for
every visitor.

How I would fix it:

Split CSS into:

- critical/global layout and typography,
- public page components,
- admin-only styles,
- report/table styles,
- optional widgets such as Select2, datepicker, and DataTables.

Keep the truly global bundle small. Load optional styles from template blocks or
component-specific includes. Start with DataTables, datepicker, Select2,
multiseek, and session-security styles because those are unlikely to be needed
on every public page.

How to verify:

- Compare compressed CSS size and first render timing before and after.
- Use browser coverage tools on representative public pages.
- Check pages that depend on moved styles to avoid visual regressions.

### JS-2 [High] Main JavaScript blocks early rendering

Evidence:

- `src/django_bpp/templates/bare.html:65`
- `src/django_bpp/templates/bare.html:80`

Why this matters:

The main JavaScript bundle and event handlers are loaded in the document head
without `defer`. The body is hidden to avoid FOUC until jQuery ready. This
couples first paint to JavaScript download, parse, and execution. On slower
connections or cold caches, users wait longer before seeing useful content.

How I would fix it:

Add `defer` to safe scripts and move initialization into deferred modules or
`DOMContentLoaded` handlers. Replace full-body hiding with small targeted fixes
for the components that actually flash. For scripts that must run early, split
them into a tiny inline bootstrap and a deferred main bundle.

How to verify:

- Measure first contentful paint and time to interactive with browser tooling.
- Check pages with Foundation, topbar, autocomplete, and dynamic forms.
- Run smoke tests for pages that previously depended on synchronous global
  script side effects.

### JS-3 [High] Freshworks support widget loads too broadly

Evidence:

- `src/django_bpp/templates/base.html:96`
- `src/django_bpp/templates/admin/base_site.html:146`

Why this matters:

Third-party support scripts add network requests, JavaScript execution, and
privacy/security surface. Loading them on every authenticated public page and
again in admin means users pay the cost even if they never open support.

How I would fix it:

Render the support button locally, but load Freshworks only when the user clicks
the button or after an idle delay. Share one loader implementation between
public and admin templates. Keep tenant/user metadata injection lazy as well,
because it is only needed once the widget is opened.

How to verify:

- Compare network waterfall before and after.
- Confirm support still opens with the right user identity and ticket context.
- Test pages where Content Security Policy or ad blockers affect third-party
  scripts.

### JS-4 [Medium] UserWay accessibility widget is injected globally

Evidence:

- `src/django_bpp/templates/base.html:299`

Why this matters:

Accessibility widgets are often heavy third-party scripts. Loading one on every
non-test public page adds cost before knowing whether a user will interact with
it. The impact is especially visible on mobile and slower machines.

How I would fix it:

Gate the widget behind a tenant setting and load it after user interaction or
browser idle time. If the widget must be visible immediately for policy reasons,
render a lightweight local launcher and lazy-load the remote script when the
launcher is activated.

How to verify:

- Measure main-thread time and network requests with and without the widget.
- Confirm accessibility requirements are still met.
- Check that the widget does not regress authenticated and anonymous pages.

### JS-5 [High] Admin globally loads many page-specific scripts

Evidence:

- `src/django_bpp/templates/admin/base.html:39`
- `src/django_bpp/templates/admin/base_site.html:211`

Why this matters:

Every admin page loads Grappelli, jQuery UI, keypad/date scripts, and BPP admin
enhancements. Some admin pages need these, but many do not. Admin users perform
repeated workflows, so global overhead accumulates quickly.

How I would fix it:

Move page-specific scripts and CSS into Django admin `Media` definitions,
template blocks, or explicit includes. Keep only the minimum admin shell script
in the base template. Start with keypad/date helpers and heavier BPP admin
enhancements because they are easier to associate with specific forms.

How to verify:

- Use browser coverage on common admin list, change, and dashboard pages.
- Check date widgets, autocomplete widgets, and custom admin forms.
- Keep a small compatibility shim if legacy inline scripts assume globals.

### JS-6 [Medium] Admin hides the whole document until window load

Evidence:

- `src/django_bpp/templates/admin/base_site.html:18`

Why this matters:

The admin template hides the whole page until `window.load` and then waits an
additional 100 ms. `window.load` waits for images, third-party scripts, and
other late resources. This delays first paint even when the HTML and critical
CSS are ready.

How I would fix it:

Identify the exact component that required the anti-FOUC workaround, likely a
widget or Select2/admin enhancement. Hide only that component until it is
initialized. Let the rest of the page render immediately.

How to verify:

- Compare first paint and visually complete timing in admin.
- Test change forms with the widgets that motivated the original workaround.
- Remove the global hiding only after confirming no visible layout flash.

### JS-7 [Medium] Favicon and small static assets should bypass Django

Evidence:

- `src/django_bpp/urls.py:346`

Why this matters:

Small public static assets such as favicon should be served by nginx or the
static-file layer with long cache headers. Routing them through Django adds
request overhead. There is also prior local evidence that the favicon/sendfile
path can produce ASGI `Content-Length` mismatch noise when the nginx sendfile
backend is used outside its intended deployment path.

How I would fix it:

Ship favicon through the static pipeline as an immutable or versioned asset.
Configure nginx/static serving for `/favicon.ico` directly. Keep a Django
redirect only if legacy compatibility is needed, and cache that redirect
aggressively.

How to verify:

- Check response headers for `/favicon.ico` in development and production.
- Confirm no Django view is hit for favicon requests.
- Watch appserver logs for disappearance of sendfile/content-length noise.

### JS-8 [High] Runtime compressor/static work belongs in build or release

Evidence:

- `docker/appserver/entrypoint-appserver.sh:38`
- `docker/appserver/entrypoint-appserver.sh:52`
- `docker/bpp_base/Dockerfile:145`
- `docker/bpp_base/Dockerfile:480`

Why this matters:

The production image already bakes static files, but appserver startup still
launches runtime static/compressor work. That creates CPU and I/O spikes during
deployment, makes startup behavior less deterministic, and risks serving before
all derived assets are ready.

How I would fix it:

Move all deterministic asset generation into the Docker build stage:
`grunt build`, `collectstatic`, compressor output, and generated error pages.
At runtime, only copy immutable baked files into the mounted static root. If a
legacy image lacks baked assets, keep the current fallback path, but treat it as
compatibility only.

How to verify:

- Compare appserver startup time and CPU usage.
- Confirm compressed assets exist in the image before runtime.
- Deploy twice quickly and verify static volume contents are overwritten by the
  baked source of truth.

## Background tasks

### BG-1 [High] Celery queues are too coarse for mixed workloads

Evidence:

- `docker/workerserver/entrypoint-workerserver.sh:5`
- `src/django_bpp/settings/base.py:677`

Why this matters:

The default worker consumes both `celery` and `denorm`. Many heavy tasks still
use the default queue. This means short interactive tasks, denorm flushes,
imports, PBN export calls, CPU-heavy reports, and retry loops can compete for
the same worker processes and prefetch behavior.

How I would fix it:

Define workload-specific queues:

- `short` for quick interactive jobs,
- `denorm` for denormalization flushes,
- `imports` for PBN/import pipelines,
- `pbn-export` for external API work,
- `reports` or `cpu` for expensive local computation,
- optionally `maintenance` for nightly rebuilds.

Run separate worker deployments with queue-specific concurrency, prefetch,
timeouts, retry settings, and memory recycle limits. Route tasks explicitly in
`CELERY_TASK_ROUTES`.

How to verify:

- Track queue latency and task runtime per queue.
- Simulate a long import and confirm short tasks still run promptly.
- Check that denorm flushes no longer starve normal background work.

### BG-2 [High] Parent Celery tasks poll child workflows

Evidence:

- `src/ewaluacja_optymalizacja/tasks/discipline_swap/analysis.py:330`
- `src/ewaluacja_optymalizacja/tasks/unpin_all_sensible.py:242`

Why this matters:

Some tasks launch chords/chains and then sleep in a loop until child work is
done. The parent task occupies a worker slot without doing useful work. Under
load, this reduces effective concurrency and can create queue backups.

How I would fix it:

Use Celery chord callbacks or a persistent workflow model. The parent task
should schedule child work and return. A callback should run when children
finish and update the workflow state. If Celery chord reliability is a concern,
store expected child counts in the database and let each child atomically mark
completion; the final child triggers the next phase.

How to verify:

- Run the workflow with worker concurrency 1 and verify it no longer deadlocks
  or idles in a polling parent.
- Track active worker slots during the workflow.
- Add tests for failed child tasks and retry behavior.

### BG-3 [High] Web views can block on denorm flush

Evidence:

- `src/ewaluacja_optymalizacja/views/pins.py:95`
- `src/ewaluacja_optymalizacja/views/capacity_analysis.py:131`
- `src/ewaluacja_optymalizacja/views/capacity_analysis.py:179`

Why this matters:

Requests that wait for denorm flush tie up web workers and create poor user
experience. A 10-minute polling loop in a view is especially risky: if several
users trigger it, the appserver can lose capacity even though the real work is
background maintenance.

How I would fix it:

Turn these actions into asynchronous jobs. The view should validate input,
enqueue the job, and redirect to a status page. The status page should read
durable workflow state and refresh via polling or channels. Denorm flush should
be one explicit phase of the job, not something the request waits for.

How to verify:

- Confirm HTTP response time is bounded and independent of denorm queue size.
- Check that users get clear job status and error messages.
- Load-test concurrent starts of the same workflow.

### BG-4 [Medium] DirtyInstance polling burns worker slots

Evidence:

- `src/ewaluacja_optymalizacja/tasks/helpers.py:349`

Why this matters:

Worker-side polling for `DirtyInstance` counts has the same problem as request
polling: it occupies capacity while waiting for another process. The helper
also documents that triggering flush directly was skipped to avoid deadlocks,
which means the task may be waiting for external progress it does not control.

How I would fix it:

Represent "waiting for denorm to drain" as a workflow state. A periodic monitor
or denorm drainer callback should advance workflows whose dependencies are
cleared. If exact callbacks are not practical, use a low-frequency scheduler
that wakes pending workflows, not long-running tasks that sleep.

How to verify:

- Ensure no Celery task stays active only to poll.
- Test behavior when denorm is delayed, failed, or already drained.
- Track worker utilization during evaluation workflows.

### BG-5 [Medium] WoS citation updates are row-by-row

Evidence:

- `src/bpp/tasks.py:69`

Why this matters:

The WoS citation task loops through universities/classes, fetches individual
objects, updates them, and saves row by row. The code also has a FIXME noting
that multiple universities repeat object queries. Row-by-row work is slower,
creates more transactions/statements, and increases lock churn.

How I would fix it:

Collect candidate primary keys per model once. Fetch objects in batches, compute
new citation values in memory, and `bulk_update` only changed rows. Avoid
per-university duplicate scans by computing the candidate set independently of
the university loop where possible.

How to verify:

- Add query-count tests for the task.
- Compare runtime and statement count on a representative dataset.
- Verify updates still respect university-specific business rules.

### BG-6 [High] Author deduplicator performs a daily full replacement

Evidence:

- `src/django_bpp/settings/base.py:694`
- `src/deduplikator_autorow/tasks.py:247`
- `src/deduplikator_autorow/tasks.py:455`
- `src/deduplikator_autorow/utils/meta.py:79`

Why this matters:

The scheduled author deduplication scan loads broad author metadata, computes
candidates, deletes previous candidates, and inserts the new set. Full
replacement is easy to reason about, but it scales poorly as author/publication
data grows and can create large write bursts.

How I would fix it:

Make the scan incremental. Track authors changed since the last successful run,
including changes caused by publication/discipline/institution updates. Rebuild
candidate buckets only for affected normalized surnames or author groups. Keep a
periodic full rebuild as a maintenance safety net, but do not make it the daily
default.

How to verify:

- Compare daily run duration and rows written before and after.
- Test that changes to author name, publication links, and institution links
  invalidate the right buckets.
- Run a full rebuild and incremental rebuild on the same data to compare output.

### BG-7 [High] PBN export enqueuer is row-by-row and task-per-record

Evidence:

- `src/pbn_export_queue/tasks.py:128`
- `src/pbn_export_queue/models.py:31`

Why this matters:

The export enqueuer loops through record IDs, fetches each object, checks for an
existing queue row, creates a row, and schedules a task. This creates many
queries and many Celery messages. Duplicate prevention is application-level, so
concurrent enqueue paths can still race.

How I would fix it:

Fetch records in bulk. Add a partial unique constraint for open queue entries,
then use `bulk_create(ignore_conflicts=True)` or database-native upsert. Replace
one-task-per-record scheduling with a bounded dispatcher task that claims and
processes batches.

How to verify:

- Enqueue thousands of records and compare query count, runtime, and broker
  messages.
- Test concurrent enqueue attempts for the same record.
- Verify retries and user-authorization holds still behave correctly.

### BG-8 [High] PBN export claiming should be database-atomic

Evidence:

- `src/pbn_export_queue/tasks.py:21`
- `src/pbn_export_queue/tasks.py:85`

Why this matters:

The worker uses cache locks to avoid duplicate work. Cache locks help, but the
selection and claim are not one database-atomic operation. Races are still
possible between selecting candidate rows and setting locks, and locks can drift
from durable queue state after worker crashes.

How I would fix it:

Claim rows inside the database using `select_for_update(skip_locked)` in a
transaction, or an atomic `UPDATE ... WHERE status = open RETURNING id`. Store
claim metadata such as `wysylke_podjeto`, worker id, and retry deadline in the
queue row itself. Use cache only as an optional fast path, not the source of
truth.

How to verify:

- Start multiple workers and verify each queue row is claimed once.
- Kill workers mid-export and confirm stale claims are recovered.
- Remove cache availability in a test environment and confirm correctness.

### BG-9 [Medium] PBN import progress should be less write-heavy

Evidence:

- `src/pbn_import/utils/base.py:21`
- `src/pbn_import/tasks.py:33`

Why this matters:

Large imports naturally want frequent progress reporting, but progress writes
should not dominate database activity. The current code saves progress JSON and
task/session state often. This can create unnecessary contention and bloat on
session tables.

How I would fix it:

Persist durable checkpoints at a lower rate and publish live progress through a
transient channel. Combine session field changes into one save. Keep the final
state and error state fully durable, but treat intermediate progress as
best-effort.

How to verify:

- Count progress writes for a fixed import.
- Check UI smoothness with transient updates.
- Force task failure and confirm recovery/error reporting still has enough
  persisted context.

### BG-10 [Medium] Author-relations rebuild is full delete plus insert

Evidence:

- `src/powiazania_autorow/core.py:48`
- `src/powiazania_autorow/core.py:90`
- `src/django_bpp/settings/base.py:714`

Why this matters:

The current SQL rebuild is set-based, which is good, but it still deletes and
recreates the whole relation table. As data grows, that can create locks,
temporary empty states inside a transaction, large WAL volume, and autovacuum
work.

How I would fix it:

For medium scale, rebuild into a staging table and swap/truncate atomically. For
larger scale, maintain relation rows incrementally for authors affected by
publication/author-link changes and keep a periodic full rebuild as a repair
job.

How to verify:

- Measure WAL volume, runtime, and lock duration of the current rebuild.
- Confirm readers never observe an empty or partially rebuilt relation table.
- Compare incremental output against full rebuild output.

## Architectural improvements

### ARCH-1 [High] Appserver boot should not perform release work

Evidence:

- `docker/appserver/entrypoint-appserver.sh:10`
- `docker/appserver/entrypoint-appserver.sh:38`

Why this matters:

The appserver entrypoint can run baseline loading, migrations, static copying,
compression, and generated page work. This makes every appserver start heavier
and mixes deployment coordination with request serving. It also increases risk
when multiple appserver replicas start at the same time.

How I would fix it:

Split deployment into explicit phases:

1. Build image with all deterministic assets.
2. Run a single release job for migrations and one-off database changes.
3. Start appservers that only copy baked static assets if needed and then serve.

Keep compatibility fallbacks for older images, but make the normal path thin and
deterministic.

How to verify:

- Appserver startup should be short and similar across replicas.
- Only the release job should run migrations.
- Static files should be identical between image build output and runtime
  static root.

### ARCH-2 [High] Cache refresh, denorm, and search rebuilds need one outbox pattern

Evidence:

- `src/bpp/migrations/0429_cache_trigger_v3.sql:38`
- `src/ewaluacja_optymalizacja/views/pins.py:95`
- `src/bpp/management/commands/rebuild_search_index.py:1`

Why this matters:

The project currently mixes row triggers, denorm dirty queues, manual rebuild
commands, Celery tasks, and synchronous waits. Each mechanism has its own
deduplication and failure behavior. That makes high-volume changes hard to
reason about and causes code paths to wait for each other.

How I would fix it:

Use a durable outbox pattern for derived data:

- triggers or model code enqueue affected keys,
- batch drainers refresh materialized/cache/search tables,
- drainers are idempotent and observable,
- workflows depend on drainer completion through durable state, not polling
  loops.

This does not require replacing every mechanism at once. Start with cache
refresh and search index, then extend the same pattern to denorm-dependent
workflows.

How to verify:

- Every queued key can be retried safely.
- Duplicate changes collapse into one refresh.
- Operators can see queue depth, oldest queued item, last successful drain, and
  failure details.

### ARCH-3 [High] Search and matching normalization should be centralized

Evidence:

- `src/import_common/core/normalize_db.py:12`
- `src/import_common/core/publikacja.py:234`
- `src/deduplikator_zrodel/utils.py:76`
- `src/crossref_bpp/utils.py:45`
- `src/przemapuj_zrodla_pbn/views.py:95`

Why this matters:

Normalization and fuzzy matching logic is repeated across import, Crossref,
deduplication, autocomplete, and source remapping. Repetition makes it hard to
index correctly because each query may express normalization slightly
differently. It also makes ranking behavior drift between workflows.

How I would fix it:

Introduce explicit match-key APIs and, where useful, match-key tables:

- publication title key,
- source title/abbreviation key,
- author name key,
- identifier keys.

The code should call a shared API for normalization and candidate lookup. The
database should index those exact keys. Workflows can still have different
ranking rules, but they should not reimplement the normalization/indexing layer.

How to verify:

- Build shared fixtures for title/source/author matching edge cases.
- Confirm all old workflows call the same candidate provider.
- Compare candidate sets and ranking before/after migration.

### ARCH-4 [High] Long-running workflows should be persistent state machines

Evidence:

- `src/ewaluacja_optymalizacja/tasks/discipline_swap/analysis.py:330`
- `src/ewaluacja_optymalizacja/views/capacity_analysis.py:131`
- `src/ewaluacja_optymalizacja/tasks/helpers.py:349`

Why this matters:

The evaluation/optimization code has both request-level waits and worker-level
polling. This is a symptom that long workflows are encoded as control flow
rather than durable state. It makes failures and retries harder, and it wastes
web/worker capacity.

How I would fix it:

Create workflow models with explicit states, for example:

- `created`,
- `queued`,
- `running_phase_1`,
- `waiting_for_denorm`,
- `running_phase_2`,
- `completed`,
- `failed`.

Each task advances the state transactionally. The UI reads state and renders
progress. Retries resume from the last durable state instead of relying on a
still-running parent task.

How to verify:

- Kill workers during each phase and confirm the workflow can resume or fail
  cleanly.
- Ensure duplicate task delivery does not corrupt state.
- Confirm users can reload the status page and see accurate progress.

### ARCH-5 [Medium] Asset pipeline should become build-time and route-aware

Evidence:

- `src/django_bpp/templates/bare.html:43`
- `src/django_bpp/templates/admin/base.html:39`
- `docker/appserver/entrypoint-appserver.sh:52`

Why this matters:

The current pipeline combines broad template-level compressor blocks with
runtime compression. This makes it harder to reason about what each page loads
and keeps runtime responsible for work that should be deterministic at build
time.

How I would fix it:

Move toward build-time hashed bundles with a manifest. Keep a small global
bundle, then add route/component bundles for admin, reports, search widgets,
charts, and support widgets. Templates should reference manifest entries, not
ask runtime compressor to discover and build bundles.

How to verify:

- Bundle sizes are visible in CI/build output.
- Runtime no longer executes compressor for normal deployments.
- Browser cache headers can be long-lived because filenames are content-hashed.

### ARCH-6 [Medium] Worker topology should be an explicit deployment contract

Evidence:

- `docker/workerserver/entrypoint-workerserver.sh:5`
- `src/django_bpp/settings/base.py:666`
- `src/django_bpp/settings/base.py:677`

Why this matters:

Once queues are split, deployment must treat worker types as separate
components. Otherwise the project can define routes but still run one generic
worker that consumes everything. Explicit topology also lets memory-heavy tasks
use stronger recycle limits and IO-heavy tasks use different concurrency.

How I would fix it:

Document and implement worker profiles:

- `worker-short`,
- `worker-denorm`,
- `worker-imports`,
- `worker-pbn-export`,
- `worker-reports`.

Each profile should specify queue names, concurrency, prefetch multiplier,
timeouts, memory limits, autoscaling policy, and whether results/events are
needed.

How to verify:

- Deployment manifests expose separate worker services.
- Queue latency dashboards are separated by worker profile.
- Killing one worker class does not stop unrelated work.

### ARCH-7 [Medium] Search-index rebuild needs an operational contract

Evidence:

- `src/bpp/management/commands/rebuild_search_index.py:1`

Why this matters:

The rebuild command is useful and carefully avoids trigger overhead, but it
looks like an operator/manual tool rather than a first-class maintenance flow.
Search index freshness is user-facing. If rebuilds are manual, stale fulltext
data can persist until someone notices.

How I would fix it:

Create a scheduled, locked, observable rebuild job. It should record start time,
end time, rows processed, errors, and last successful completion. It should
support dry-run/count-only mode and batch progress. If the outbox pattern from
ARCH-2 is implemented, full rebuild becomes a repair/maintenance command rather
than the primary freshness mechanism.

How to verify:

- Expose last successful rebuild in admin or metrics.
- Ensure only one rebuild can run at a time.
- Test interrupted rebuild recovery.

### ARCH-8 [Medium] Add performance observability for the identified hot paths

Evidence:

- `src/django_bpp/settings/base.py:1446`
- `src/django_bpp/settings/base.py:207`

Why this matters:

The codebase has many performance-sensitive paths, but static review cannot
prove the exact production ranking. Without query and task metrics, regressions
will keep appearing as user-facing slowness or deployment-time surprises.

How I would fix it:

Add dashboards and tests around the hot paths in this report:

- `pg_stat_statements` top queries by total time and mean time,
- queue depth and oldest message per Celery queue,
- task runtime histograms per task name,
- denorm/cache refresh queue depth,
- search/import query-count tests,
- `EXPLAIN` snapshots for critical matching queries.

Do not gate every change on heavy benchmarks. Use focused tests for known hot
paths and lightweight runtime metrics for production drift.

How to verify:

- Dashboards show the top database queries and slowest tasks.
- New index/trigger changes can be compared before/after.
- CI catches accidental N+1/query-count regressions on selected workflows.

## Suggested implementation order

1. Add observability around PBN queue selection, trigram matching, and cache
   refresh before changing behavior.
2. Add normalized identifier/name/title indexes and rewrite the most expensive
   matching queries to use them.
3. Split Celery queues and remove parent-task polling from the highest-volume
   workflows.
4. Move runtime static/compressor work to the image build/release path.
5. Start the durable cache refresh queue behind a feature flag.
6. Convert denorm-dependent web flows into asynchronous workflow-state pages.
7. Incrementalize daily deduplication and author-relation maintenance jobs.

## Validation checklist

- Run `EXPLAIN (ANALYZE, BUFFERS)` for the top fuzzy matching queries before
  and after index work.
- Benchmark bulk publication updates and imports on a production-like dump.
- Track Celery queue latency before and after worker split.
- Measure appserver startup time before and after static/compressor relocation.
- Use browser coverage and network waterfalls for representative public and
  admin pages.
- Add query-count tests for source deduplication and PBN export enqueueing.
- Add failure/retry tests for long-running workflow state transitions.
