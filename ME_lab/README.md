# ME Lab Inventory App Spec

This folder currently holds the planning brief for the future `ME_lab` app.

The goal is to turn the existing shared desktop inventory platform into a machine shop / mechanical engineering variant that follows the same overall pattern as `TE_Lab`, while using ME-specific fields, import rules, and terminology.

## Purpose

Create an `ME_lab` inventory app for machine shop materials and equipment that:

- reuses `shared_core` wherever possible
- starts from the `Lab_Template` app structure rather than copying `TE_Lab` directly
- keeps the familiar desktop workflow already used in `TE_Lab`
- supports ME-specific inventory fields and reporting needs

## Current Status

What is already true:

- `TE_Lab` is the current working reference application
- `shared_core` contains the reusable database, importer, GUI, export, and reporting code
- `Lab_Template` is the clean starter for new lab variants
- `ME_lab` is not an app implementation yet; it is still a planning/spec folder

What this document is for:

- define the intended ME app behavior clearly enough to guide implementation
- separate confirmed requirements from assumptions and open questions
- highlight which parts are likely configuration-only and which may require shared-core changes

## Source Context

This spec is based on:

- `ME_lab/Machine_Shop_Inventory_System.txt`
- `ME_lab/App.png`
- root `README.md`
- the current app structure used by `TE_Lab` and `Lab_Template`

Primary business reference:

- Aditya's Excel file: `Machine Shop Material List`

Planned deployment/storage reference:

- `S:\Manufacturing\Internal\_Syed_H_Shah`

## Product Goal

The ME app should provide a searchable desktop inventory tool for machine shop inventory records, with a table-first workflow and a more detailed record view for editing and review.

It should feel like the same product family as `TE_Lab`, not a separate custom application.

## MVP Scope

The first implementation should focus on the smallest useful ME version:

- create a real `ME_lab` app folder from `Lab_Template`
- configure the app identity, filenames, and database naming for ME
- import inventory data from the primary ME source file
- display records in the shared table-based desktop UI
- support global search and column filtering
- allow users to open and edit a full record by double-clicking a row
- preserve Excel export
- preserve HTML export in a form that is still easy to customize outside the app

## Out Of Scope For MVP

These items are valuable, but should not be treated as required for the first pass unless decisions are made explicitly:

- multi-source import logic equivalent to TE's current master-plus-survey flow
- project-aware grouping or sectioned UI behavior
- full image management workflow for item photos
- any major UI redesign beyond ME-specific labels and fields
- schema changes in shared code that are not needed for the first usable version

## Confirmed Requirements

### Core Record Fields

The ME app is expected to track at least:

- quantity
- manufacturer
- model
- description
- box number
- location

### User Workflow

Expected user flow:

1. User opens the ME inventory app.
2. User sees a searchable table of ME inventory records.
3. User searches by meaningful terms such as manufacturer, model, description, location, or other stored values.
4. User double-clicks a row to open the detailed record view.
5. User reviews or edits the full record.
6. User exports data to Excel or HTML when needed.

### MVP Table View

The default ME table view should likely prioritize:

- quantity
- manufacturer
- model
- description
- box number
- location

Other fields can remain available in the detailed record view or through later filtering/export decisions.

### Detail View Expectations

The detailed record view should:

- show more information than the table view
- remain editable using the existing shared app pattern
- include a place for an item picture

### Export Expectations

- keep the current detailed Excel export capability
- keep HTML output easy to customize externally
- avoid hard-coding HTML formatting in ways that make future ME-specific customization difficult

### Search Expectations

Search should work across the meaningful stored record data.

Current notes suggest the existing TE search behavior may not always match user expectations, so ME implementation should verify search behavior carefully rather than assuming it is already sufficient.

## Field Definitions

These definitions are intended to guide implementation and import mapping.

| Field | Meaning | Notes |
| --- | --- | --- |
| `quantity` | Count of identical items or available units | Likely maps cleanly to shared `qty` |
| `manufacturer` | Company or maker name | Already supported in shared code |
| `model` | Model number or identifying part/model label | Already supported in shared code |
| `description` | Human-readable item description | Already supported in shared code |
| `box number` | Storage box/bin/cabinet reference | Not currently a dedicated shared field |
| `location` | Physical storage or room location | Already supported in shared code |

## Assumptions

These are working assumptions, not final decisions:

- the first ME version will likely use one primary Excel file instead of TE's current two-file import pattern
- `ME_lab` should be created from `Lab_Template`, then adjusted only where ME differs
- the shared table/search/edit/export workflow should remain the baseline UX
- `quantity` can probably reuse the existing shared `qty` field
- HTML export can remain based on the shared export pipeline, with ME-specific customization handled outside the app when possible

## Technical Implications

### Likely App-Level Work

The following work is likely app-specific and should not require major shared-core changes by itself:

- create a real `ME_lab` app folder from `Lab_Template`
- define ME app metadata in `app_config.py`
- choose ME-specific source filenames and output filenames
- add/import the ME source data file into the app `Data/` workflow
- update text labels so the app presents itself as an ME inventory tool

### Likely Shared-Core Review Points

The following areas need explicit implementation review because they may require shared model, schema, importer, GUI, or export changes:

- `box number`, because there is no dedicated box-number field in the current shared `Equipment` model or database schema
- item pictures, because the current shared edit/detail UI does not include image fields or image preview/storage behavior
- project separation, because it is not currently represented in the shared table, schema, or filters
- ME import shape, because the current startup/import flow expects both `master_source_file` and `survey_source_file`
- ME table columns, because the current shared table is oriented around TE fields and does not currently show `quantity` or `box number`
- search behavior validation, because the current shared search already covers many fields but should still be tested against ME terminology and expected queries

### Design Preference

Use the smallest viable implementation first:

- prefer reusing existing shared fields before adding new schema
- prefer app-specific parsing/configuration before changing shared runtime behavior
- only extend shared-core when the ME requirements cannot be represented cleanly with the current model

## Open Questions

These decisions should be resolved before implementation gets too far:

- Is `Machine Shop Material List` the only ME import source, or will there be a second source file?
- Should `box number` become a real shared schema field, or stay ME-specific in notes/import mapping?
- Should project separation be a stored field, a filter/grouping concept, or just reporting metadata?
- How should pictures be represented: file paths, copied local assets, or links to a shared drive?
- Which ME fields must appear in the table view versus only in the detailed view?
- Does ME need its own customized HTML report structure, or is the current shared export shape sufficient at first?

## Future Enhancements

These are good follow-on ideas once MVP is working:

- project-based filtering or grouping
- richer image support for records
- ME-specific HTML report templates
- improved search tuning based on real user queries
- support for additional ME source files if the inventory process expands

## Recommended Next Implementation Step

Before creating the actual `ME_lab` app implementation, confirm the following:

1. whether ME has one input file or more than one
2. whether `box number` must be a first-class stored field
3. whether picture support is required for MVP or can be deferred
4. whether project separation is MVP scope or future scope

Once those are decided, the next practical build step should be to copy `Lab_Template` into a real ME app folder structure and map the ME source file into the existing shared import/export flow.
