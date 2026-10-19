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
