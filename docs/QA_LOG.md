# QA log

How the application was exercised as different people, what broke and what was fixed. Re-run these checks after any UI or action change.

## Method
1. **Page crawl as every role** (Estimator, Procurement Reviewer, Commercial Approver, Administrator, Viewer) on the synthetic tender: every reachable page, recording HTTP errors, browser console errors, failed requests and sideways page overflow.
2. **Action probe**: every registered action (169) called as every role with empty and with plausible-but-wrong inputs; a clean refusal or message is a pass, any HTTP 500 or leaked exception text is a defect.
3. **Form sweep in a real browser** as each role: every form on every page filled with sample data and submitted (hundreds of submissions per role); any 500, "UNEXPECTED_ERROR", traceback or browser exception is a defect.
4. **Phone width** (390 px): no page may scroll sideways.

## Defects found and fixed
| # | Found by | Defect | Fix |
|---|---|---|---|
| 1 | Action probe | Saving a project edit with nothing changed built an empty SQL SET and returned HTTP 500 | `Database.update` ignores an empty change; the service says `NO_CHANGES` |
| 2 | Form sweep | The label-capitalising script changed the text of dropdown options that have no `value`, so the browser submitted "Unverified" instead of "unverified" and a norm could not be created (database rule) | Option values are pinned before the displayed text changes; the norm service validates enum fields; any database rule violation in an action becomes a plain `DATA_RULE` message |
| 3 | Review | The error page printed the error message as raw HTML (reflected-markup risk) and was unstyled | Styled, auto-escaped error pages with a reference id; unexpected errors are logged, never shown |
| 4 | Review | Approvals linked rates to a page that did not exist (404) | Link fixed; a test follows every link the inbox offers |
| 5 | Review | No logo or favicon, system fonts without fallbacks for Arabic | SVG logo and favicon, font stack with Arabic fallbacks, nothing loaded from outside |
| 6 | Review | Viewer saw live forms that could only fail | Viewer mode: banner and all write forms disabled |
| 7 | Phone test | Header, menu and tables overflowed sideways at 390 px | Compact header, scrolling menu, single-column grids |
| 8 | Rates upload run | Candidates without a VAT treatment could not be approved and the inbox did not say why | Blockers shown with an inline fix form; VAT can be stated for a whole file |

## Final sweep
After the fixes: 1,309 form submissions in a real browser across the five roles (estimator 218, procurement 247, commercial 275, administrator 307, viewer 262), no server error, no unexpected error, no browser exception; all pages load for every role; no page scrolls sideways at phone width.

## UX audit as a first-time user (light and dark)
Method: an automated pass over 41 pages (every project section, rates, libraries, approvals, every Settings tab) as the Administrator in light and dark, checking page structure (one h1, named controls, leaked template text, empty states) plus axe-core (WCAG 2 A/AA and best-practice), followed by a read-through for "can I tell what this is, what to do next and why?".

| # | Finding | Fix |
|---|---|---|
| 1 | 518 form controls had no accessible name (axe: label, select-name, label-title-only) | Names from label / column heading / field name, added in `app.js`; icon-only header cells named |
| 2 | Contrast below 4.5:1 for muted text and green status tags (1,527 nodes, light) | Darker `--muted` and `--ok`; dark theme passed |
| 3 | **Navigation redesign leaked a template variable:** the sidebar's `cur` shadowed the tender-pack page's own `cur`, so the pack page showed an empty pack ("pack r") and a broken manifest link | Renamed to `navcur`; test added |
| 4 | Estimate page printed `<Macro 'item'>` in a heading (macro named `item` shadowed a page variable) | Macro renamed `navlink`; test added |
| 5 | Heading levels skipped (h6 menu labels, h3 under h1) | Menu labels are not headings; stage/readiness/pack titles are h2 |
| 6 | Links in running text distinguishable by colour only | Underlined |
| 7 | Scrollable code boxes not keyboard reachable; white box in dark mode | `tabindex=0`; token colours |
| 8 | Inputs & parameters page showed raw JSON | Readable "Field: value" lines |
| 9 | Several pages still had `PRJ-xxxx - Section` headings | One title per section from the menu definition |
| 10 | Empty lists said only "No records." | Friendlier, explains that records appear as they are added |
| 11 | Jargon without explanation | 254 glossary terms behind ⓘ icons; placeholders reduced to examples |

After the fixes the same audit reports **0 axe-core violations on all 41 pages in both light and dark**. The five remaining notes are intentional: three tables that show only headers until data exists, an empty-state message that already tells the person what to do, and the word "undefined" inside a sentence about unclear scope. Not covered: screen-reader testing by a person, Microsoft Edge/Safari rendering.

## BOQ upload, BOQ builder, price list (24 Oct 2026)
Run in a browser as estimator and procurement, plus the full suite (508 tests).

| # | Found | Fix |
|---|---|---|
| 1 | Approve / Needs verification buttons clipped on candidate rows (desktop and phone) | Button column sizes to its content; single column on phones |
| 2 | A real 6-trade client BOQ imported 0 lines (two-row headings, QTY/UNIT headings swapped, repeated `a.`/`b.` codes, total lines, PSC/LOT units) | Importer reads stacked headings, swaps back with a warning, composes sub-item codes, skips total lines, new unit spellings; 177 lines, matches an independent cell count |
| 3 | BOQ builder form (about 1,040 boxes) refused by the server's 1,000-field limit | Limit raised; page sends only filled boxes |
| 4 | Rates upload form posted a single sheet, so a per-trade price list imported only the first trade | "All trade sheets" option; covered by a test |
| 5 | Approvals inbox cut the rate-candidate queue at 200 | Limit 5,000 |

Not covered: real-world price quality. Web-sourced prices are indicative and unverified (see `KNOWN_LIMITATIONS.md`).

## Not covered
Microsoft Excel itself, live public sources, real rates and real users: see `KNOWN_LIMITATIONS.md`.
