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

## Not covered
Microsoft Excel itself, live public sources, real rates and real users: see `KNOWN_LIMITATIONS.md`.
