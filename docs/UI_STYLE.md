# UI style: buttons and controls

One system, defined at the end of `app/web/static/app.css` ("Button and control system"). Do not add new button styles in templates; pick a variant.

| Use | Class | Look |
|---|---|---|
| Main action (Approve, Save, Import, Create) | none | solid blue |
| Secondary action (Cancel, Re-check, Download, Filter) | `alt` | white with blue outline |
| Reject, Deactivate, Remove | `danger alt` | white with red outline, red text |
| Irreversible final action (rarely needed) | `danger` | solid red |
| Quiet / tertiary | `ghost` | no border |
| Compact (inside tables and inline forms) | add `sm` | 30 px instead of 36 px |

Rules: every button and text field is 36 px high (30 px with `sm`); same radius, weight, focus ring and disabled look everywhere; approve and reject always appear as a pair with the same width and a reason/comment box beside each; a Viewer sees all write buttons disabled; on phones labels wrap instead of widening the page. Links that look like buttons use `class="btn ..."` with the same variants.

## Navigation
Inside a project the sidebar becomes the project menu (`app/web/projnav.py` is its only definition): a back link, the project card, then seven numbered groups in the order the work is done - Start here, Tender documents, Quantities, Pricing, Programme, Commercial, Controls & submission - and a collapsed "Everywhere else" group for the global pages. The group holding the current page is open; the current page is highlighted; each page shows a breadcrumb (Projects > project > group > page), a title equal to its menu label and a one-line purpose. A new page is added by adding one line to `projnav.GROUPS`. Outside a project the sidebar is the global menu.

## Look, font and dark mode
* **Font:** Plus Jakarta Sans (SIL OFL, licence in `app/web/static/fonts/`), served from our own origin (variable weight, latin and latin-ext subsets, `font-display: swap`); the fallback stack is the system UI fonts plus Arabic fallbacks. Nothing is loaded from outside (CSP `default-src 'self'`). Body is 14.5 px / 1.55.
* **Colours are tokens** (`:root` custom properties at the top of `app.css`). Never write a literal colour in a template; use `--surface`, `--muted`, `--accent`, `--ok/--warn/--bad` (+ `-bg`, `-line`), `--on-accent`.
* **Dark mode:** the same tokens are redefined under `:root[data-theme="dark"]` and, when the person has not chosen, under `prefers-color-scheme: dark`. The header button toggles light/dark; the user menu offers Light / Dark / System. The choice is kept in `localStorage` key `ksa-theme`; `theme.js` is loaded in `<head>` so the page never flashes the wrong theme. Contrast is checked in both themes with axe-core (see `QA_LOG.md`).

## Help system (the ⓘ icon)
* One glossary: `app/web/helptext.py` (`TERMS`, keyed by the *normalised* label text, and `PLACEHOLDERS`). `/glossary.json` serves it to `help.js`; `norm()` is implemented identically in Python and JavaScript (a test checks they agree).
* `help.js` adds a hover/focus/tap ⓘ next to a known heading, column title or field label (once per page for repeated words), shows it in one tooltip element, and is keyboard reachable (`tabindex=0`, Esc closes).
* **Placeholders hold examples only** ("e.g. DWG-102 rev B"). If a placeholder used to explain something, the explanation moves to the ⓘ and the placeholder is rewritten. Add a term by adding one line to `helptext.py`; never put explanatory prose in a placeholder.
* `app.js` gives every field an accessible name (its label, column heading or field name) and every icon-only header cell a hidden name, so screen readers and tooltips have something to say.
* Empty lists say what they are for (`.empty`), never just "No records".
