"""Regenerates .claude/skills/*/SKILL.md (the skill text is maintained here so all of them stay structurally identical). Run: python scripts/gen_skills.py"""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent / ".claude" / "skills"

COMMON_PROHIBITED = [
    "Measuring, inferring or generating quantities, or editing a quantity without an approved change request.",
    "Inventing prices, wages, productivity, wastage, suppliers, FX/tax values or benchmarks; filling a missing value with a default or a guess.",
    "Calling an approve/reject/publish function as, or on behalf of, a human; writing `approvals`, status or `audit_log` rows directly; weakening `app/approvals/policy.py` or a reconciliation rule.",
    "Editing or overwriting original files in `1. Tender Documents/` or any supplier-supplied original.",
    "Treating AI output, an extract, a summary or an index as authoritative over the original document.",
]

SKILLS = {}

def skill(name, description, tools, hint=None, manual=False, **sec):
    SKILLS[name] = dict(description=description, tools=tools, hint=hint, manual=manual, sec=sec)

skill("project-initializer",
 "Create a new construction project with its numbered workspace, project CLAUDE.md and manifest, then walk the human through recording context and the first documents. Use when the user asks to start/set up a new project or tender.",
 "Read, Glob, Grep, Bash(python -m app.cli *), Bash(ls *)", "<project name> [client] [location]", manual=True,
 purpose="Start a project correctly: a unique project ID, the ten numbered folders, a generated project `CLAUDE.md` and `project.json`, and a checklist of what a human must still record. Never confuses the project workspace with the global libraries.",
 when="A new tender/job must be set up; a legacy project lacks a workspace (use `project refresh`); the workspace folders were damaged or deleted.",
 inputs="Project name (required); client, tender reference, location/region, project type, applicable trades, design stage (optional, human-supplied); an authenticated user with an author role (`KSA_CLI_USER`, `KSA_CLI_PASSWORD`). Do not guess missing facts — leave them blank.",
 read=["CLAUDE.md (root)", "docs/PROJECT_WORKSPACES.md", "docs/DATA_MODEL.md", "app/services/projects.py", "app/services/workspaces.py", "data/regions/regions.csv (valid region codes)"],
 steps=["Check the database is initialised: `python -m app.cli coverage` must show resources > 0 (otherwise run `python -m app.cli init --demo-users` first).",
        "List existing projects with `python -m app.cli project list` so the user does not create a duplicate by mistake (project IDs are generated and unique).",
        "Create: `python -m app.cli project create --name \"…\" --client \"…\" --location \"…\" --project-type \"…\" --trades \"Architectural,HVAC,…\" [--tender-ref …] [--design-stage …] [--demo]` (add `--demo` only for SYNTHETIC test projects).",
        "Verify the tree: `ls projects/<PRJ-…>/` shows the ten numbered folders plus `CLAUDE.md` and `project.json` (names and numbers are fixed).",
        "Open `projects/<id>/CLAUDE.md`: confirm facts match what the user said and the 'No BOQ imported yet' issue is listed. Do not edit the generated block; put notes under *Human notes*.",
        "Tell the human the next actions: copy tender documents into `1. Tender Documents/`, run the project-indexer skill, import the BOQ (boq-import-review skill), record approved drawing/specification revisions (web UI *Workspace & documents* → `update_project`; **only a human states these**).",
        "Optionally write `projects/<id>/4. Clarifications & Assumptions/setup_checklist.md` using the schema below."],
 outputs="`projects/<PRJ-ID>-<slug>/` (10 folders, `CLAUDE.md`, `project.json`) and DB rows `projects`, adopted `project_assumptions`, audit entry. Optional `setup_checklist.md`: sections `## Recorded facts`, `## Missing facts (human to supply)`, `## Next actions`, each a bullet list; no invented values.",
 validate=["Exactly one folder matches `<PRJ-ID>-*`; `project.json.project_id` equals the DB id.", "Re-running `project refresh <id>` changes no file contents except generated files (idempotent).", "`python -m pytest tests/workspaces -q` still passes if you touched workspace code."],
 approval="Creating a project needs an author role (Estimator, Procurement Reviewer, Commercial Approver, Administrator). Nothing is approved by this skill. Drawing/specification revisions, trades and policy assignment are human decisions.",
 failure=["`Conflict: Project … already exists` → do not retry with force; pick another ID or open the existing project.", "`WORKSPACE_CONFLICT` → a folder belongs to another project; stop and ask the user; never delete or rename it.", "Auth error → ask the user for credentials; never read or print passwords from files.", "Folder permissions/disk errors → report them verbatim."],
 extra_prohibited=["Hard-coding project details into the root `CLAUDE.md`.", "Creating folders by hand with different names/numbers."])

skill("project-indexer",
 "Inventory and text-extract a project's documents into `2. AI Context/` (versioned, non-authoritative) and report what needs human review. Use after documents are added or changed, or when asked what documents a project has.",
 "Read, Glob, Grep, Bash(python -m app.cli *)", "<PRJ-ID>",
 purpose="Create/refresh the searchable document index (`project_documents`, `project_index.json`, `project_summary.md`, `extracts/docNNNNN_vN.txt`) without touching originals.",
 when="New tender documents/addenda/revisions arrived; before requirements extraction; when a source file changed (flagged *Source changed - review*).",
 inputs="Project ID; documents already placed in the workspace by a human. Authenticated author user.",
 read=["projects/<id>/CLAUDE.md", "docs/PROJECT_WORKSPACES.md (indexer section)", "app/services/project_index.py"],
 steps=["Run `python -m app.cli project index <PRJ-ID>`; read the printed counts (new/changed/unchanged/missing/extracted/not_extracted/errors).",
        "Open `projects/<id>/2. AI Context/project_summary.md`: list files *Not text-extracted* (CAD/BIM, scanned PDFs, unsupported types) and *Extraction error* with the stored reason.",
        "For each *Source changed - review* or *Missing* document, tell the human which file and why; they decide whether the new revision supersedes the old (use the UI *Mark reviewed* or `mark_document_reviewed`). Do not mark reviewed yourself on their behalf unless they explicitly ask you to act as their session user.",
        "Use `python -m app.cli project search <id> \"term\"` to locate text; always open the **original** file to confirm any fact before relying on it.",
        "Report revisions seen in file names as *observations*; never write them into the project's approved drawing/spec revision fields."],
 outputs="`2. AI Context/project_index.json` (schema `ksa-estimator/project-index/1`; per document: id, rel_path, file_name, file_type, size_bytes, modified_at, sha256, area, category, trade_hint, revision, extraction_status, extraction_error, extract_version, extract_path, text_chars, review_status), `project_summary.md`, `extracts/`.",
 validate=["`unchanged` equals the file count on an immediate re-run (idempotent).", "A changed file produced a *new* extract version and the old extract file still exists.", "Every extraction failure has an `extraction_error` message; none is silently skipped.", "Originals' hashes unchanged."],
 approval="None for indexing. Marking a document *Reviewed* is a human acknowledgement (informational; it approves no estimating data).",
 failure=["Parser missing/corrupt/encrypted/scanned PDF → record as indexed but not text-extracted (the tool does this); tell the user an OCR or a PDF plot is needed — do not paraphrase the drawing.", "File > 150 MB → indexed without hash/extract; report.", "Workspace missing → run `project refresh <id>` first."],
 extra_prohibited=["Summarising drawings/specifications from memory or from partial extracts as if complete.", "Deleting old extract versions."])

skill("boq-import-review",
 "Import a client BOQ/takeoff file and review the import report (rejected rows, ambiguous units, duplicates, change requests) for the human. Use when a BOQ or revised BOQ arrives.",
 "Read, Glob, Grep, Bash(python -m app.cli *), Bash(python -m pytest *)", "<PRJ-ID> <boq file>",
 purpose="Bring human-measured quantities into the project exactly as supplied, surface every problem, and leave all decisions (unit choices, quantity changes, mapping) to humans.",
 when="First BOQ import; BOQ revision/re-import; reviewing why items were rejected or flagged.",
 inputs="Project ID, BOQ/takeoff file (CSV/XLSX; ideally from `templates/boq_import_template.xlsx`), revision label from the human. No quantity may come from anywhere but the file.",
 read=["docs/IMPORT_EXPORT_FORMATS.md", "app/imports/boq.py (FIELDS, detect_header, parse_rows)", "app/services/boq.py (change requests, mapping)", "docs/APPROVAL_WORKFLOW.md (BOQ rows)", "projects/<id>/CLAUDE.md"],
 steps=["Keep the original in `1. Tender Documents/` (do not move it). Preview: UI *BOQ import → upload* or POST `/api/projects/<id>/boq/preview`; check the detected header row/column mapping; if required columns are unmapped, ask the human for the mapping.",
        "Import: `python -m app.cli project import-boq <PRJ-ID> <file> --revision <label>` (or the UI with explicit mapping). A copy is stored in `3. BOQ & Takeoff/<sha10>_<name>`.",
        "Read the summary: items new/unchanged, headings, blank rows, `rejected_rows` (code + reason), `needs_review`, `duplicates`, `change_requests`, `missing_in_revision`, `by_trade`.",
        "Write the review note (schema below) listing every rejected row, ambiguous/unknown unit, duplicate code, zero/negative/text quantity and every pending change request with old→new values.",
        "Tell the human what only they can decide: choose canonical units for ambiguous ones (e.g. `ton` → `t`), approve/reject quantity change requests, acknowledge duplicate flags with a reason (`acknowledge_issues`), correct the source file where wrong.",
        "Do not map or price here; hand over to the estimating-workflow skill."],
 outputs="`3. BOQ & Takeoff/boq_import_review_<revision>.md` with sections `## Summary` (counts), `## Rejected rows` (row, code, reason), `## Unit decisions needed`, `## Duplicates`, `## Change requests (old → new)`, `## Questions for the client`. DB: `boq_imports`, `boq_items`, `boq_rejected_rows`, `change_requests` (Pending Review).",
 validate=["`items + headings + blank + rejected` accounts for every source row (`rows_read`).", "Original quantity text is retained per item; no quantity changed outside a change request.", "Re-importing the same file creates 0 new items and 0 change requests.", "`python -m pytest tests/imports -q` passes if importer code changed."],
 approval="Importing needs an author role. Unit choices, quantity changes and mapping are approved by an Estimator/Commercial Approver/Administrator (`boq_unit`, `boq_quantity`, `boq_mapping`). This skill never approves them.",
 failure=["`MAPPING_INCOMPLETE`/`NO_HEADER` → show detected columns, ask for the mapping; never guess a column.", "`MALFORMED_FILE` → ask for a re-export; do not repair data by hand.", "Archived project → read-only; ask the Commercial Approver to unarchive."],
 extra_prohibited=["Replacing 'TBA' or blank quantities with numbers; deleting rejected rows; merging duplicates silently."])

skill("requirements-extraction",
 "Extract contractual/technical requirements from indexed tender documents into a cited requirements register and DRAFT clarifications/scope entries for human review. Use after indexing tender documents.",
 "Read, Glob, Grep, Bash(python -m app.cli *)", "<PRJ-ID> [document or trade]",
 purpose="Turn specification/ITT text into a traceable list of requirements, assumptions to confirm, exclusions and clarification questions — each with a verbatim quote and location — so humans can price correctly. It produces proposals only.",
 when="Tender documents are indexed and the estimator needs a requirements/clarification list, or an addendum arrived.",
 inputs="Project ID with indexed documents; optional scope (a document, a trade). Original documents are read directly where extracts are partial.",
 read=["projects/<id>/CLAUDE.md", "projects/<id>/2. AI Context/project_summary.md", "docs/ASSUMPTIONS_POLICY.md", "app/services/registers.py", "app/ai/service.py (`ai_draft_clarifications`, `ai_suggest_scope_gaps`, `deterministic_scope_checks`)", "docs/APPROVAL_WORKFLOW.md (AI section)"],
 steps=["List candidate sources with `project search <id> \"term\"` (e.g. 'shall', 'exclude', 'provisional', 'warranty', 'testing', 'approved make') and open each ORIGINAL file at the cited place; extracts may be partial or mis-ordered.",
        "For each requirement record: verbatim quote (short), file, page/section, category (scope / technical / commercial / programme / compliance / exclusion), trade/cost code, and *proposed action* (price it / raise clarification / add exclusion or qualification / note assumption). Mark anything unclear as a question, not a requirement.",
        "Write `projects/<id>/4. Clarifications & Assumptions/requirements_register.md` and a JSON twin (schema below).",
        "Offer the human drafts: clarification questions (`add_clarification` – status Open) and scope entries (`add_scope_entry` – status Draft, human approves). Create them only when the user asks you to act as their authenticated session; otherwise list them.",
        "Run `scope_checks` (deterministic) if the BOQ exists and report findings as suggestions (`ai_suggestions`, Pending Review)."],
 outputs="`requirements_register.md` + `requirements_register.json`: array of `{id, quote, source_file, location, category, trade, cost_code, proposed_action, confidence_note, status: \"Proposed\"}`. `confidence_note` is free text (e.g. 'scanned page, partial extract') — never a numeric score presented as fact.",
 validate=["Every item has a source file and location and its quote is found verbatim in that original (grep it).", "No item states a quantity, price or rate that is not literally in the source.", "Items from extracts that could not be verified against the original are marked 'unverified'."],
 approval="Clarification resolution and scope entries require human approval (`clarification`, `exclusion`); AI/heuristic suggestions need human acceptance (`accept_suggestion`). Nothing here becomes a decision on its own.",
 failure=["Scanned/CAD-only documents → say so; request text-searchable PDFs; do not infer content.", "Conflicting clauses → record both with locations as a clarification candidate; do not choose.", "Document Arabic/English mismatch → record both texts; do not translate as authoritative."],
 extra_prohibited=["Converting requirements into quantities or rates.", "Marking a clarification resolved or a scope entry approved."])

skill("assembly-management",
 "Create, review and version assembly (unit-rate build-up) definitions safely: explicit waste and productivity bases, no double counting. Use when adding or editing assemblies or mapping items to them.",
 "Read, Glob, Grep, Bash(python -m app.cli *), Bash(python -m pytest *)", "<assembly code or task>",
 purpose="Keep assemblies structurally correct and auditable. Assemblies carry consumption factors, **not prices**; factors are supplied by humans with a source.",
 when="Adding/changing an assembly; checking why an assembly cannot be approved; mapping BOQ items; importing assembly sheets.",
 inputs="Assembly code, unit, cost code, line definitions (resource ids, factors, waste basis, productivity basis, crew) **provided or confirmed by the estimator with their source**. Resources must exist.",
 read=["docs/ESTIMATING_METHODOLOGY.md (sections 2–3)", "docs/ASSUMPTIONS_POLICY.md", "app/services/assemblies.py (`validate`, `add_line`)", "app/estimators/direct_cost.py", "data/assemblies/standard_assemblies.csv", "docs/EXTENDING.md"],
 steps=["Search for an existing assembly first (`/assemblies?code=…` or `assemblies.list_assemblies`); prefer `clone_assembly`/`new_assembly_version` to creating duplicates.",
        "Create: action `create_assembly`, then `add_assembly_line` per line. Material: `factor`, `factor_unit`, and exactly one waste approach (`factor_includes_waste` OR `waste_basis` = fixed_pct/assumption — never both). Labour: `productivity_basis` (paid_hours_per_unit | productive_hours_per_unit | output_per_crew_shift) and crew if used. Plant: utilisation basis. Subcontract: say what the lump sum includes (prevents double count). Nested assemblies: no cycles.",
        "Run validation (`assemblies.validate`) and read every error; fix the definition, not the validator.",
        "Hand to the human to `submit_assembly` and have an Estimator/Commercial Approver `approve_assembly`. Approved versions are immutable — edit via `new_assembly_version`.",
        "Confirm effect: freeze nothing; run the estimate (UI Estimate build-up) and inspect the line `basis` text for the assembly."],
 outputs="DB: `assemblies` (+version), `assembly_lines`; audit entries. Optional `4. Clarifications & Assumptions/assembly_notes_<code>.md` recording the human-given source of each factor.",
 validate=["`assemblies.validate` returns no errors; no `DOUBLE_WASTE`, no missing productivity basis, no cycle.", "Every factor has a stated human source in `source`/notes; none invented.", "`python -m pytest tests/unit/test_direct_cost.py tests/unit/test_library_data.py -q` passes."],
 approval="Assembly approval: Estimator, Commercial Approver or Administrator (`policy.py` `assembly`). AI cannot approve. Project-scoped assemblies still need approval.",
 failure=["Validation errors → report them; never bypass with direct SQL.", "Unknown resource → create the resource (no price) via `create_resource`, then continue.", "Approved assembly needs a change → new version, not an edit."],
 extra_prohibited=["Typing consumption/productivity/waste numbers from memory or 'industry norms'.", "Adding prices to assemblies."])

skill("estimating-workflow",
 "Run and interpret the end-to-end estimating workflow for a project: mapping → build-up → procurement needs → indirects/commercial → reconciliation → versions → gated export, stating what is blocked and which human must act. Use when asked 'where is this estimate', 'what blocks submission', or to progress a project.",
 "Read, Glob, Grep, Bash(python -m app.cli *), Bash(python -m pytest *)", "<PRJ-ID>",
 purpose="Give an accurate, evidence-based status and next human actions; run deterministic steps the user's role permits; never push anything past a gate.",
 when="Progressing or reviewing a project; explaining Preliminary state; before a submission.",
 inputs="Project ID; the user's authenticated session for any write. For read-only status, only the database.",
 read=["projects/<id>/CLAUDE.md", "docs/ESTIMATING_METHODOLOGY.md", "docs/APPROVAL_WORKFLOW.md", "docs/USER_GUIDE.md (walkthrough)", "app/estimators/estimate.py (`_blockers`)", "app/reporting/completeness.py"],
 steps=["Read status: UI *Completeness* tab or `app.reporting.completeness.project_completeness`; note Blocked/Open rows and the estimate state (Complete / Complete with Provisional Inputs / Preliminary — Incomplete).",
        "Missing rates: run `detect_needs` (procurement-rfq skill). An approved real rate is required per line; explain that the global library has no approved real rates until imported (rate-update-review skill). Provisional (project-scoped) approvals need a human reason.",
        "Assumptions: list those in use but unapproved (Assumptions tab / dashboard); humans approve.",
        "Indirects/duration/policy/tax: propose via the UI/actions; Commercial Approver approves policy and tax category (tax needs verification evidence).",
        "Run reconciliation (`run_reconciliation`); review findings by severity; exceptions only where the rule allows and with a documented human reason; Critical never waived.",
        "Freeze a version (`freeze_version`; a snapshot is stored), submit, Commercial Approver approves; offer approved; tender export approved; only then `export_submission`. Preliminary outputs are always available and watermarked.",
        "Report a table: step · state · blocking item · responsible role."],
 outputs="Status report (chat or `9. Reconciliation & Approvals/status_<date>.md`): `## State`, `## Blocking items` (table: item, why, role who can resolve, where in UI), `## Open items`, `## Next three actions`. Frozen versions: DB + `5. …/versions/*_inputs_snapshot.json`.",
 validate=["Every blocking item cites the exact blocker string or finding id from the system.", "Numbers quoted come from the engine/UI, not mental arithmetic.", "After freezing: `python -m app.cli project verify-snapshot <version_id>` shows ok."],
 approval="Estimate final approval, offer approval and tender export approval are Commercial Approver/Administrator decisions; supplier selection and rate approval are Procurement/Commercial decisions. Never perform them for a human.",
 failure=["`STALE_VERSION` → inputs changed; freeze a new version.", "`RECON_BLOCKED` → resolve findings; do not lower severities.", "`ESTIMATE_PRELIMINARY` → unresolved inputs remain; list them."],
 extra_prohibited=["Using `include_unapproved` (preliminary) numbers as a tender price.", "Exporting a submission-ready package without the recorded approvals."])

skill("rate-source-research",
 "Research and record public data sources for Saudi construction rates/indices (access, terms, format) in the Source Register and access log, and implement or update a provider if a permitted, documented route exists. Use when looking for rate sources or when an adapter must be built/changed.",
 "Read, Glob, Grep, Edit, Write, Bash(python -m pytest *), Bash(python -m app.cli sources *), WebFetch, WebSearch", "<source or topic>", manual=True,
 purpose="Find out what is genuinely available, legally and technically, and record it honestly — successes, partial reads and blocks — without fabricating data or circumventing controls.",
 when="Searching for new official/public datasets; GASTAT/KAPSARC/Etimad/open-data questions; a provider breaks; before adding a provider.",
 inputs="A topic or URL; knowledge of what network access exists (direct HTTP may be blocked in cloud sandboxes). Prefer official documentation.",
 read=["docs/KSA_DATA_SOURCES.md", "data/sources/source_register.csv", "data/sources/ACCESS_LOG.md", "docs/RATE_UPDATE_WORKFLOW.md", "app/sources/base.py (AccessPolicy, HttpFetcher)", "app/sources/providers.py", "tests/sources/test_rate_pipeline.py"],
 steps=["Check the register/access log first; do not repeat a documented blocked attempt in a loop.",
        "Locate official documentation for the dataset/API (not mirrors) and read the licence/terms text actually shown; note what you could not read.",
        "Prefer downloadable files or documented APIs. Fetch sparingly (one request per question; respect robots.txt, rate limits, auth walls, CAPTCHAs). If blocked, record the exact error and URL once and stop.",
        "Record in `data/sources/source_register.csv` (id, url, dates, geography, currency, unit basis, trades, licence conditions *as read*, extraction method, access status, limitations, confidence) and append numbered rows to `ACCESS_LOG.md`; run `python scripts/gen_docs.py`.",
        "Save any retrieved data **verbatim** under `data/public_data/<name>/` with a `PROVENANCE.md` (request URL, date, tool used, what it is and is not).",
        "If a documented, permitted route exists: add/extend a provider in `app/sources/providers.py` with an explicit `AccessPolicy`; write offline tests with `FakeFetcher`/recorded fixtures; set `live_verified` text to what was actually observed. If not: mark manual-only and document the manual import path.",
        "Import samples via `python -m app.cli index import … --dry-run` first (indices) or `rates validate` (price lists)."],
 outputs="Updated `source_register.csv`, `ACCESS_LOG.md`, `docs/KSA_DATA_SOURCES.md` (regenerated table), optional `data/public_data/<name>/` files + `PROVENANCE.md`, provider code + tests. Status vocabulary: Accessed / Partially accessed / Blocked / Not attempted.",
 validate=["Every fact in the register cites where it was read; unread terms are stated as 'not reviewed'.", "No price copied from a source whose terms forbid reuse; no third-party aggregator treated as official.", "`python -m pytest tests/sources tests/approvals/test_source_boundary.py -q` passes; no test touches the network."],
 approval="Source selection and any data enabled for estimating are human decisions. Imported prices become candidates (Pending Review) — see rate-update-review. A provider never approves or publishes.",
 failure=["403/tunnel/robots refusal → log BLOCKED with the exact message; document the manual alternative; do not retry in a loop or use another route to bypass.", "Terms unclear → treat as not reusable; record 'terms not reviewed'.", "Unexpected data shape → store the raw response, do not coerce; report."],
 extra_prohibited=["Bypassing authentication, CAPTCHAs, paywalls, robots.txt or rate limits; scraping Etimad or any site in bulk.", "Presenting an index (CCI) or a tender award value as a market unit price.", "Shipping a supplier list or prices you did not read from a legitimate source."])

skill("rate-update-review",
 "Review the rate-candidate queue with a human: verify evidence, basis (VAT/delivery/unit/currency), matching and normalisation, then guide approve-for-publication → publish → rate approval. Use when candidates are pending or after an import/refresh.",
 "Read, Glob, Grep, Bash(python -m app.cli *)", "[queue name | candidate ref]", manual=True,
 purpose="Make human review fast and rigorous. The skill prepares evidence and recommendations; the decisions are made by authorised humans through the application.",
 when="After `rates import`, `sources refresh`, or a web-watchlist run; weekly queue review; before relying on any new rate.",
 inputs="Queue/candidate refs; the reviewing user's role; the original source (open the URL/file yourself to confirm).",
 read=["docs/RATE_UPDATE_WORKFLOW.md", "docs/RATE_PROVENANCE.md", "app/rate_updates/candidates.py (`publishable_price`, `classify_queue`)", "app/rate_updates/normalise.py", "docs/APPROVAL_WORKFLOW.md"],
 steps=["List: `python -m app.cli rates pending [--queue Conflicting]`; open `/rates/updates/<RC-ref>` for evidence and flags.",
        "For each candidate verify against the ORIGINAL source: price, currency, unit, VAT statement, delivery/installation, date/validity, geography, specification equivalence to the resource. Note contradictions and stale dates.",
        "Matching: if `resource_id` is empty, check the suggestion (`suggested_resource_id`) against the resource specification; only a human sets it (`edit_rate_candidate`).",
        "Normalisation: confirm each step (FX row approved and date-valid; unit factor physical; VAT from approved category). If inputs are missing, say which approvals/records a human must create first (e.g. approve an FX rate).",
        "Prepare a recommendation per candidate: approve / needs verification (what to ask) / reject (why). Conflicting queue: compare both sources and recommend one with reasons.",
        "Present to the human. They decide with `rates review <ref> approve|reject|needs_verification --comment …` (needs Procurement Reviewer/Commercial Approver/Administrator). Then `rates publish <ref>` (creates a *Pending Review* version) and a human approves the rate (`approve_rate`).",
        "After approval: confirm the old version is `Superseded` (kept), frozen estimates are unchanged (`project verify-snapshot`), and re-run reconciliation on affected projects."],
 outputs="`rate_review_<date>.md` (e.g. in `9. Reconciliation & Approvals/` of the relevant project or `var/`): table `ref | resource | original price/unit/currency | source | basis | normalisation | recommendation | reason`. DB changes only through the human actions above.",
 validate=["Recommended 'approve' items pass `publishable_price` (price, resource, VAT basis, price kind, complete normalisation).", "Original price in the candidate equals the source; the evidence snippet matches.", "No candidate is approved for a price kind of Promotional/Quote required/Specification only."],
 approval="Candidate review: Procurement Reviewer / Commercial Approver / Administrator (`rate_candidate`). Rate approval: same roles (`rate`). Estimators may only propose, edit matching fields, publish approved candidates, or approve provisionally for one project with a reason. AI: never.",
 failure=["`NOT_PUBLISHABLE` → show the listed reasons; fix the data (human) or reject.", "`SELF_APPROVAL_BLOCKED` → another reviewer must act.", "Source unreachable now → keep 'Needs verification'; do not approve from memory."],
 extra_prohibited=["Running `rates review … approve` or `approve_rate` yourself without the human reviewer explicitly acting as themselves.", "Changing original price/currency/source fields; bulk-approving a queue."])

skill("subcontractor-quote-analysis",
 "Analyse subcontractor/supplier quotations for a package: completeness, scope gaps, exclusions, tax/delivery basis, normalisation and like-for-like comparison, producing a recommendation for the human reviewer. Use when quotations are received.",
 "Read, Glob, Grep, Bash(python -m app.cli *)", "<PRJ-ID> <package id>",
 purpose="Make levelling transparent: quoted prices stay as quoted; normalised/comparison values are separate; every difference is explained; selection remains a human decision.",
 when="Quotes arrive for an RFQ package; before a supplier selection; to check an expired/low-confidence quote.",
 inputs="Quotation records or files in `6. Procurement & Quotations/`; the package id; the specification. Quote text may be pasted for optional AI extraction (review-only).",
 read=["docs/PROCUREMENT_GUIDE.md", "app/procurement/quotes.py", "app/procurement/leveling.py (`level_package`)", "app/procurement/selection.py", "app/ai/service.py (`ai_extract_quotation`, `spec_diff`)", "docs/APPROVAL_WORKFLOW.md"],
 steps=["Ensure each quotation is entered against the project/package (`create_quotation`, `add_quote_line` or `import_quotation_lines`) with the supplier's own figures, validity, currency, tax treatment, delivery/unloading, exclusions and deviations — copied from the document, blanks left blank.",
        "A Procurement Reviewer verifies each quotation against the original (`approve_quotation`); AI-extracted data needs explicit verification.",
        "Level: UI *Compare quotations* or `leveling.level_package`. Read coverage, missing items, tax/FX/unit normalisation, `spec_differences`, expired quotes, lowest like-for-like.",
        "Build the analysis note (schema below): scope coverage matrix, exclusions that shift cost to the contractor, deviations, validity/lead time, payment terms, price per normalised unit, risks.",
        "Recommend (not decide): preferred supplier(s) with reasons; if not lowest like-for-like, draft the justification text for `propose_selection`. Adjustments (`add_adjustment`) are proposals until approved.",
        "After human approval of the selection, `publish_rates` creates *Pending Review* rates; each still needs rate approval."],
 outputs="`6. Procurement & Quotations/quote_analysis_<package>_<date>.md`: `## Quotations received`, `## Coverage matrix`, `## Exclusions & deviations`, `## Normalised comparison (quoted vs normalised, shown separately)`, `## Recommendation & rationale`, `## Open questions to suppliers`.",
 validate=["Quoted totals equal the supplier documents; normalised totals reproduce from stated FX/tax/unit steps.", "Every missing item is listed, not priced.", "No supplier contact or price is invented; no email is sent."],
 approval="Quotation verification, supplier selection (value threshold may require a Commercial Approver), adjustments and rate publication are human approvals (`quotation`, `supplier_selection`, `rate`).",
 failure=["Quote expired → mark/flag; request re-validation; exclude from selection.", "Foreign currency without approved FX → leave unnormalised and say why.", "Non-comparable scope → do not force a ranking; list the gaps."],
 extra_prohibited=["Selecting a supplier; waiving a not-like-for-like difference; averaging quotes into a rate."])

skill("procurement-rfq",
 "Detect procurement needs from the estimate and prepare RFQ packages (English/Arabic drafts, XLSX/DOCX) for manual issue. Use when rates are missing/expired or when an RFQ is requested.",
 "Read, Glob, Grep, Bash(python -m app.cli *)", "<PRJ-ID> [package]",
 purpose="Turn unpriced/expired/low-confidence lines into clear RFQ packages. The application never sends email and never invents supplier contacts.",
 when="Estimate shows unpriced lines; rates expired; a specification changed; a human asks for an RFQ.",
 inputs="Project ID; supplier ids from the supplier directory (human-created); response deadline from the human; specifications from the BOQ/assemblies/documents.",
 read=["docs/PROCUREMENT_GUIDE.md", "app/procurement/needs.py", "app/procurement/rfq.py", "templates/rfq_template.xlsx", "projects/<id>/CLAUDE.md"],
 steps=["Run `detect_needs` (UI *Procurement & RFQs* or POST `/api/actions/detect_needs`). Review the register: reason code, exposure (indicative only when an unapproved rate exists; otherwise 'unknown').",
        "Check each item's specification text against the tender documents (use project search + originals). Add missing specification via the procurement item update (human-confirmed).",
        "Create RFQs per package (`create_rfq`; language en/ar; deadline). Export XLSX/DOCX or copy the email text; the Arabic text is a draft for human review.",
        "Give the human the files from `6. Procurement & Quotations/` to issue manually; they press *Mark issued* (`mark_rfq_issued`) after sending.",
        "When quotes return use subcontractor-quote-analysis."],
 outputs="RFQ files `RFQ-…xlsx/docx` in `6. Procurement & Quotations/`; DB `procurement_packages`, `procurement_items`, `rfqs`, `rfq_items`. Optional `rfq_cover_note_<package>.md`: scope summary, clarifications, deadline — all from recorded data.",
 validate=["Every RFQ line has description, specification (or an explicit 'to be confirmed' note), quantity and unit from the BOQ/takeoff; no price or budget appears in the RFQ.", "No supplier address/email appears unless recorded by a human.", "`python -m pytest tests/procurement -q` passes if procurement code changed."],
 approval="Creating RFQs needs an author role; issuing is a manual human act. Supplier qualification (`qualify_supplier`) and later selection are human approvals.",
 failure=["No supplier recorded → leave the supplier blank; ask the human to add one (`create_supplier`).", "Missing specification → raise a clarification or ask the estimator; never write one from memory."],
 extra_prohibited=["Sending email or contacting suppliers; disclosing the estimate's internal rates or budget in an RFQ."])

skill("gantt-duration-estimation",
 "Build a CPM programme from human-supplied tasks and derive a project duration proposal for indirect costs. Use when duration/time-related indirects must be estimated.",
 "Read, Glob, Grep, Bash(python -m app.cli *), Bash(python -m pytest *)", "<PRJ-ID>",
 purpose="Compute a transparent duration from tasks, durations and dependencies the estimator provides, and propose it (never approve it) so time-based indirects can resolve.",
 when="Indirects use per-day/week/month methods; programme changed; a duration is missing or unapproved.",
 inputs="Task list with id, name, duration (working days), predecessors — **given by the estimator** with the basis for each duration; working-calendar assumptions (`calendar.working_days_per_week/month`, approved by a human). Optional labour-hours-derived cross-check.",
 read=["app/estimators/duration.py", "app/services/indirects.py (`set_tasks`, `propose_duration_from_schedule`, `propose_duration`)", "docs/ESTIMATING_METHODOLOGY.md (duration/indirects)", "docs/ASSUMPTIONS_POLICY.md", "tests/unit/test_indirect_duration.py"],
 steps=["Collect the tasks and their basis from the human; record in `7. Programme & Indirects/programme_inputs.md` (schema below). Do not derive durations from drawings or from 'typical' productivities.",
        "Check calendars: working days/week and per month must be approved assumptions; otherwise the conversion to months is unresolved — report it.",
        "Load tasks (`indirects.set_tasks`) and run CPM (`duration.cpm`) via `propose_duration_from_schedule`; inspect critical path, total working days, cycle errors.",
        "Optionally cross-check with `labour_derived_months` using hours from the estimate and a crew size the human gives; show both and the difference.",
        "Propose the duration (`propose_duration` with source_type and basis note); the human approves (`approve_duration`). Time-based indirects remain unresolved until then."],
 outputs="`7. Programme & Indirects/programme_inputs.md`: table `id | task | duration (working days) | predecessors | basis (who/what)`; `programme_result.md`: critical path, total days, months, calendar assumptions used; DB `schedule_tasks`, `project_durations` (Pending Review).",
 validate=["No cycles; every predecessor id exists; total = longest path (hand-check one path).", "Months conversion uses the approved calendar assumption values quoted in the note.", "`python -m pytest tests/unit/test_indirect_duration.py -q` passes."],
 approval="Project duration approval: Estimator, Commercial Approver or Administrator (`project_duration`); an AI-proposed duration needs a reviewer comment.",
 failure=["Cycle detected → list the cycle; ask the human to fix dependencies.", "Calendar assumption unapproved → duration stays unresolved; say which assumption.", "No task data → stop and ask; do not fabricate a programme."],
 extra_prohibited=["Inventing task durations or productivity; approving the duration."])

skill("reconciliation-check",
 "Run and interpret the reconciliation (cost vs schedule vs offer vs assumptions vs procurement) and prepare a human-readable remediation list. Use before freezing/approving an estimate or when findings are asked about.",
 "Read, Glob, Grep, Bash(python -m app.cli *), Bash(python -m pytest *)", "<PRJ-ID>",
 purpose="Find and explain every discrepancy and the correct fix path; exceptions are human decisions governed by rule severity.",
 when="Before `freeze_version`/approval/export; after rate or assumption changes; to explain a blocked approval.",
 inputs="Project ID; authenticated user to run (`run_reconciliation` needs an author role).",
 read=["config/reconciliation_rules.json", "app/reconciliation/engine.py", "app/reconciliation/rules.py", "docs/APPROVAL_WORKFLOW.md (final gate, exceptions)", "tests/reconciliation/test_recon.py"],
 steps=["Run `run_reconciliation` (UI *Reconciliation* or POST action). Note run id and `open_by_severity`.",
        "Group findings by rule code and severity; for each give: what it means, entity, financial impact, the system place to fix it, and the role who can resolve it.",
        "Distinguish *fix the data* (missing rate, unapproved assumption, expired quotation, unmapped item, totals mismatch) from *accept an exception* (only where the rule allows; reason ≥ 10 characters; High needs a Commercial Approver; Critical never).",
        "After humans fix items, re-run until no blocking-severity finding remains (blocking = Critical + High unless configured otherwise).",
        "Write the remediation list (schema below)."],
 outputs="`9. Reconciliation & Approvals/reconciliation_remediation_<run>.md`: `## Run`, `## Blocking findings` (table: id, rule, severity, entity, impact, fix, role), `## Non-blocking`, `## Exceptions proposed (for human decision)`. The engine also writes `reconciliation_report_*.xlsx` to the same folder when exported.",
 validate=["Counts in the note equal the engine's counts for that run id.", "A fresh run was executed after any fix (fingerprint-keyed exceptions only apply to unchanged findings).", "No severity or tolerance was edited to make findings disappear (`config/reconciliation_rules.json` untouched unless the human asked and approved)."],
 approval="Exceptions: roles per rule (Estimator/Procurement for low, Commercial Approver for High, never Critical). Final approval and export are separate human approvals.",
 failure=["Run errors → report the exception text; do not hand-edit findings.", "Stale findings → re-run.", "Blocking findings remain → state that final approval/export is blocked."],
 extra_prohibited=["Lowering a rule's severity, widening tolerances or accepting exceptions on behalf of a human."])

skill("excel-validation",
 "Generate, validate and (with LibreOffice) recalculate the master/standalone workbooks and check round-trip imports. Use when workbooks are generated, changed, received back from a user, or when `app/excel/spec.py` changes.",
 "Read, Glob, Grep, Bash(python -m app.cli *), Bash(python -m pytest *), Bash(soffice *)", "<workbook file> [PRJ-ID]",
 purpose="Prove workbooks are structurally sound, formulas compute, and imports create only drafts — and state clearly what was not tested (Microsoft Excel).",
 when="After changing `app/excel/*`; before sending a workbook; when a user returns an edited workbook; after regenerating templates.",
 inputs="A workbook path; optionally a project id to compare with the database. LibreOffice (`soffice`) for recalculation.",
 read=["docs/EXCEL_WORKBOOK_GUIDE.md", "docs/EXCEL_DATA_DICTIONARY.md", "app/excel/spec.py", "app/excel/roundtrip.py (`validate_workbook`)", "app/excel/recalc.py", "tests/excel/test_workbooks.py"],
 steps=["Regenerate templates if the spec changed: `python -m app.cli templates` then `python scripts/gen_docs.py`.",
        "Export a populated master: `python -m app.cli export-workbook <PRJ-ID> --out <file>` (UI download writes to `5. Estimate & Cost Build-Up/`).",
        "Verify: `python -m app.cli verify-workbook <file> --project <PRJ-ID>` → read `structure_ok`, `missing_sheets`, `header_problems`, `overwritten_formulas`, `stale`, `recalculated`, `formula_errors`, `mismatches`, `formulas`.",
        "For a user-edited file import via the UI/API round-trip (`import_master`): only drafts/proposals are created; status columns are ignored. Review the import report.",
        "State what was verified: LibreOffice recalculation yes/no; Microsoft Excel not available unless you actually ran it.",
        "Run `python -m pytest tests/excel -q`."],
 outputs="Verification JSON from the CLI (paste into the report) and optional `5. Estimate & Cost Build-Up/workbook_verification_<date>.md`: file, project, sheets, formula count, errors, mismatches, stale flag, tool versions, limitations.",
 validate=["27 required sheets present, keys/headers unchanged, no formula cell replaced by a constant, `formula_errors` empty, `mismatches` empty, workbook fingerprint equals the current estimate (else *stale*)."],
 approval="None for validation. Importing edits creates proposals; approvals still happen in the application.",
 failure=["`soffice` missing/timeouts → report recalculation as not performed (`recalculated: false`); do not claim success.", "`overwritten_formulas` non-empty → ask the user to restore formulas; do not import.", "`stale` → regenerate from the current database."],
 extra_prohibited=["Editing formulas in an exported workbook to 'fix' mismatches (fix the engine/spec instead); claiming Excel compatibility beyond what was tested."])

skill("architecture-maintenance",
 "Keep code, schema, tests and documentation consistent when changing the application: migrations, new modules/trades/sources, doc updates, instruction files. Use for any non-trivial code change or when the documentation may be out of date.",
 "Read, Glob, Grep, Edit, Write, Bash(python -m pytest *), Bash(python -m app.cli *), Bash(python scripts/gen_docs.py), Bash(git status *), Bash(git diff *), Bash(git log *)", "<change description>",
 purpose="Prevent drift: the root `CLAUDE.md`, `docs/*`, tests and migrations must describe and cover what the code really does; approval boundaries stay intact.",
 when="Before and after implementing a feature, migration, provider, importer or trade; when asked to audit or update documentation.",
 inputs="The change request; `git status` (never overwrite uncommitted user changes); the branch you were told to use.",
 read=["CLAUDE.md", "docs/ARCHITECTURE.md (status table)", "docs/DATA_MODEL.md", "docs/TESTING.md", "docs/EXTENDING.md", "docs/DEVELOPMENT_AUDIT.md", "docs/NEXT_STEPS.md", "app/migrations/ (latest file)"],
 steps=["`git status`, `git log -3`, run `python -m pytest -o addopts=\"\" -q` for a baseline; note failures before editing.",
        "Locate the owning layer (estimators pure / services DB / api actions / web / cli). Keep calculation pure, approvals in services via `authorize`, exposure through `api/actions.py`.",
        "Schema change → new numbered SQL file in `app/migrations/` (never edit an applied one); update `docs/DATA_MODEL.md` and any backup/export code that lists tables.",
        "Add tests first or alongside (independent expected values for money; fake fetchers for network; `tmp_path` for files; nothing may write into the repo).",
        "Update the capability record in `docs/capability_matrix.json` (status only changes with its acceptance test automated), then `python scripts/gen_capability_matrix.py`; `tests/unit/test_capability_matrix.py` must stay green.",
        "Update docs: the specific doc, the status table in `docs/ARCHITECTURE.md` (implemented / partial / planned), `docs/NEXT_STEPS.md`, `docs/KNOWN_LIMITATIONS.md`, root `CLAUDE.md` if commands/structure/rules changed; run `python scripts/gen_docs.py`.",
        "Run the full suite; commit on the designated branch with a clear message; push with `git push -u origin <branch>`; report the real outcome. Do not open a PR unless asked; never touch `main`."],
 outputs="Code + migration + tests + docs in one commit series; an updated `docs/DEVELOPMENT_AUDIT.md` entry for anything that deviated from earlier claims.",
 validate=["Full suite green; new behaviour has tests; `git diff --stat` shows docs changed with code.", "`tests/approvals` pass (AI boundary, source boundary); no new path writes approvals/status outside services.", "Docs distinguish implemented / partial / planned honestly (no 'complete' for a stub)."],
 approval="Changes that touch roles, gates, severities or approval records require explicit user instruction; otherwise do not alter them.",
 failure=["Failing baseline → record it in the audit doc; do not mask it.", "Migration needed for existing data → provide a dry-run script, backup, report (see `workspace_migration.py`).", "Push failure → retry only on network errors with backoff; report the final state truthfully."],
 extra_prohibited=["Force-push, reset, history rewrite, merging into `main`, deleting project data.", "Committing `projects/*`, `var/`, `.env`, client documents or secrets; putting model identifiers in repository artifacts."])

skill("governed-inputs-and-analysis",
 "Record company-supplied numbers (productivity factors, hire terms, calendar, escalation, payment terms, benchmark ranges, take-off factors, statutory rules ...) as governed parameters with their sources, then run the read-only analyses (roll-up, programme, loading, man-hours, risk, cash flow, earned value ...). Use when the user supplies factors/terms/ranges or asks for an analysis or a Basis of Estimate.",
 "Read, Glob, Grep, Bash(python -m app.cli *), Bash(python -m pytest *)", "<PRJ-ID> [report name]",
 purpose="Turn evidence the human provides into validated, versioned, approvable parameters - and use them - without ever supplying a value yourself. Analyses and proposals inform decisions; people approve.",
 when="The user gives you factors, rates of recovery, terms, ranges or a calendar from their records; they ask for a loading histogram, man-hours, risk analysis, cash flow, escalation, earned value, benchmark check, method comparison or a Basis of Estimate.",
 inputs="Project ID; the user's evidence for every number (document/record/contract clause) - without a source the parameter is refused; an authenticated author user. If a number is missing, **ask**; never fill it.",
 read=["CLAUDE.md (root)", "docs/GOVERNED_PARAMETERS.md", "docs/ANALYSIS_REPORTS.md", "docs/MTO_TEMPLATES.md", "app/estimators/param_kinds.py", "app/reporting/registry.py"],
 steps=["List kinds: `python -m app.cli param kinds`; pick the kind that matches the user's evidence; read its field skeleton (names only).",
        "Propose with the user's exact figures: `python -m app.cli param propose KIND CODE '<json>' --project <PRJ> --source \"<where the number comes from>\" [--submit]`. Validation errors are returned verbatim - fix the input with the user, do not adjust numbers to pass.",
        "Tell the human which role approves the kind (see the doc table) and that only *Approved* values enter a strict estimate. Do not call approve yourself unless the user explicitly asks you to act as their own signed-in session.",
        "Run reports: `python -m app.cli report <PRJ> <name> [--param k=v] [--save]`; read the `note`, `notes` and `estimate_state` fields and repeat them to the user. A report that stops for a missing input is correct behaviour - say what is missing.",
        "For take-off derivation: `mto preview` first, confirm the driver quantity is the **user's measured figure** (or the BOQ quantity), then `mto apply`; remind the user that the item is now a Pending Review pricing decision.",
        "For proposals (`propose_*`): they create Draft indirect items; tell the user to review and submit/approve them in *Indirects & commercials*.",
        "Generate the Basis of Estimate with the `generate_boe` action and list the six sections the estimator must still write."],
 outputs="`governed_params` rows (Draft/Pending), saved `analysis_runs` (immutable, not approvals), Draft indirect items from proposals, `5. Estimate & Cost Build-Up/basis_of_estimate/BoE_*.md/.docx`.",
 validate=["Every proposed parameter has a source quoted from the user; none was derived, defaulted or rounded by you.", "A report's `tie_out` fields are true where present (roll-up, loading, man-hours).", "After running proposals the estimate totals are unchanged until a human approves.", "`python -m pytest tests/unit/test_governed_params.py -q` passes if you touched parameter code."],
 approval="Parameters: the roles listed per kind in `docs/GOVERNED_PARAMETERS.md` (AI never). Analyses need no approval and approve nothing. Indirect proposals and pricing decisions use the existing approvals.",
 failure=["`PARAM_SOURCE` / `PARAM_FIELD` -> ask the user for the missing evidence/field.", "`CALENDAR_REQUIRED`, `TERMS_NONE`, `ESC_NONE`, `RISK_NONE`, `BASELINE_NONE` -> the report needs an approved input: explain which and stop.", "`MTO_FACTORS_MISSING` -> list the slots without an approved factor; do not skip slots unless the user decides to (explicit skip is recorded)."],
 extra_prohibited=["Proposing a factor, percentage, range, rate or hours figure from your own knowledge or 'typical' practice.", "Using the output of an analysis as if it were an approved estimate or adding it to the price without the normal approval.", "Stating that a client's or owner's standards are met."])

skill("client-profile-loading",
 "Load a client's or owner's estimating requirements from the controlled documents the user is authorised to provide into a versioned client profile, link it to a project and keep the compliance matrix honest. Use when the user supplies client estimating requirements, forms or procedures.",
 "Read, Glob, Grep, Bash(python -m app.cli *)", "<PRJ-ID> <profile code>",
 purpose="Make owner requirements traceable (document, revision, clause) and checkable, without claiming compliance with anything that has not been loaded and traced.",
 when="The user provides an owner's estimating procedure, form list, code list or deliverable requirements and wants them checked on a project.",
 inputs="The owner's documents as provided by the user (with their ids/revisions); the user's decision which requirements are mandatory. Do not rely on memory of any owner's standards.",
 read=["CLAUDE.md (root)", "app/services/profiles.py", "app/estimators/profile_checks.py", "docs/ESTIMATING_CAPABILITY_MATRIX.md (records SAU-06, SAU-07)"],
 steps=["Read the provided documents; list each requirement with `req_id`, category, title and **source_ref** (document id + revision + clause). Skip anything you cannot trace to a clause.",
        "Where a requirement can be tested on measured facts (see `profile_checks.FACT_HELP`), give `fact`, `op`, `value` exactly as the document states; otherwise leave it as a manual attestation.",
        "Create the profile: `python -m app.cli profile create CODE \"Name\" --client \"…\" --requirements reqs.csv --documents @docs.json`; then `profile submit ID`; a Commercial Approver runs `profile approve ID`.",
        "Link: `python -m app.cli profile link <PRJ> CODE`. Humans record evidence: `profile attest <PRJ> REQ Met \"evidence ref\"`.",
        "Report with `report <PRJ> compliance`; repeat the generated statement verbatim, including its scope sentence."],
 outputs="`client_profiles`, `profile_requirements`, `project_profiles`, `profile_assessments`; the compliance matrix report.",
 validate=["Every requirement has a source_ref; mandatory flags match the user's instruction.", "No requirement was added from memory or inference.", "The compliance statement is quoted unchanged."],
 approval="Profile approval: Commercial Approver / Administrator. Attestations: any author role, with evidence. AI never approves or attests.",
 failure=["`PROFILE_REQ`/`PROFILE_CHECK` -> fix the requirement with the user.", "Document not provided -> say that no requirements are loaded and that no statement can be made."],
 extra_prohibited=["Writing requirements from general knowledge of any owner's standards (e.g. Saudi Aramco).", "Claiming or implying compliance with an owner's standards."])

def render(name, d):
    s = d["sec"]
    fm = ["---", f"name: {name}", f"description: {d['description']}", f"allowed-tools: {d['tools']}"]
    if d["hint"]:
        fm.append(f"argument-hint: {d['hint']}")
    if d["manual"]:
        fm.append("disable-model-invocation: true")
    fm.append("---")
    L = fm + ["", f"# {name}", "", "## Purpose", s["purpose"], "", "## When to use", s["when"], "", "## Required context and inputs", s["inputs"], "",
              "## Read first (exact modules, data files, docs)"]
    def _fmt(r):
        if " (" in r:
            a, b = r.split(" (", 1)
            return f"- `{a}` ({b}"
        return f"- `{r}`"
    L += [_fmt(r) for r in s["read"]]
    L += ["", "## Steps"] + [f"{i}. {x}" for i, x in enumerate(s["steps"], 1)]
    L += ["", "## Outputs and schemas", s["outputs"], "", "## Validation checks"] + [f"- {x}" for x in s["validate"]]
    L += ["", "## Approval requirements", s["approval"], "", "## Failure handling"] + [f"- {x}" for x in s["failure"]]
    L += ["", "## Explicitly prohibited"] + [f"- {x}" for x in COMMON_PROHIBITED + s.get("extra_prohibited", [])]
    L += ["", "_Skills orchestrate application functions; they never bypass validation or server-side approvals. AI output remains a suggestion until an authorised human accepts it._", ""]
    return "\n".join(L)

for n, d in SKILLS.items():
    d["sec"]["extra_prohibited"] = d["sec"].pop("extra_prohibited", [])
    (ROOT / n).mkdir(parents=True, exist_ok=True)
    (ROOT / n / "SKILL.md").write_text(render(n, d), encoding="utf-8")
print(len(SKILLS), "skills written")
