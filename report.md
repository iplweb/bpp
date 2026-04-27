# Ticket #316: Możliwość stworzenia rozdziału bez wydawnictwa nadrzędnego

## Problem

The publication importer (`importer_publikacji`) allowed creating chapters
(`Wydawnictwo_Zwarte` records with `charakter_formalny.charakter_ogolny == "roz"`)
without a parent publication (`wydawnictwo_nadrzedne`). This created orphan chapter
records — chapters that don't belong to any book — which violates the data model's
semantic constraint. The bug was triggered by BibTeX imports of `@inbook`/`@incollection`
entries, where the importer's source step (step 3) had no UI for selecting a parent
publication.

## Changes

### 1. `src/importer_publikacji/models.py`
- Added two nullable ForeignKey fields to `ImportSession`:
  - `wydawnictwo_nadrzedne` → `bpp.Wydawnictwo_Zwarte`
  - `wydawnictwo_nadrzedne_w_pbn` → `pbn_api.Publication`

### 2. `src/importer_publikacji/migrations/0005_importsession_wydawnictwo_nadrzedne.py`
- New migration adding both FK fields to `ImportSession`.

### 3. `src/importer_publikacji/forms.py`
- Added `wydawnictwo_nadrzedne` and `wydawnictwo_nadrzedne_w_pbn` `ModelChoiceField`
  fields to `SourceForm` (both `required=False`, conditional validation in view).

### 4. `src/importer_publikacji/views.py`
- Added `_is_chapter()` helper to detect chapters by `charakter_ogolny`.
- Modified `_source_context()` to pass `is_chapter` flag and parent publication
  objects for Select2 pre-population.
- Modified `SourceView.post()` to validate that chapters have exactly one parent
  publication (either BPP or PBN, not both, not neither).
- Modified `_create_wydawnictwo_zwarte()` to set `wydawnictwo_nadrzedne` and/or
  `wydawnictwo_nadrzedne_w_pbn` on the created record.

### 5. `src/importer_publikacji/templates/.../step_source.html`
- Added conditional UI block for chapters: shows two Select2 autocomplete fields
  for parent publication selection (BPP book or PBN publication).
- Added JavaScript to initialize Select2 AJAX on both fields using existing
  autocomplete URLs (`wydawnictwo-nadrzedne-autocomplete`,
  `wydawnictwo-nadrzedne-w-pbn-autocomplete`).

### 6. `src/importer_publikacji/templates/.../step_review.html`
- Added display of parent publication in the review step summary table.

## How to Verify

1. Start the development server and open the publication importer.
2. Import a BibTeX `@inbook` or `@incollection` entry.
3. On step 2 (Verify), confirm the charakter formalny is set to a chapter type.
4. On step 3 (Source), verify:
   - The parent publication section appears with "Rozdział wymaga wydawnictwa
     nadrzędnego" callout.
   - Two Select2 fields are shown: "Wydawnictwo nadrzędne (BPP)" and
     "Wydawnictwo nadrzędne (PBN)".
   - Attempting to proceed without selecting a parent shows validation error.
   - Selecting both a BPP and PBN parent shows mutual exclusivity error.
   - Selecting exactly one parent allows proceeding.
5. On step 5 (Review), verify the parent publication appears in the summary.
6. After creation, verify the `Wydawnictwo_Zwarte` record has `wydawnictwo_nadrzedne`
   set correctly.
7. Import a regular book (non-chapter) and verify step 3 does NOT show the parent
   publication fields.
