# Do's and don'ts

A one-page rulebook for everyone who uses the application. The same rules are enforced by the software; this page explains them in plain words.

## Do
* **Measure quantities yourself.** Import them from your own take-off or the client's BOQ. The application never reads drawings and never invents a quantity.
* **Give every number a source.** Rates, productivity norms, calendars, payment terms, tax and FX values each need a document, quotation or approved record behind them.
* **Use the Rates workbook** (Libraries, Rates workbook) to bring in prices in bulk: download the template, fill it, upload it, check the preview, then import. Every row becomes a *candidate* that a different person must approve.
* **Work the Approvals inbox.** Anything marked Pending Review stays out of strict estimates until an authorised, different person approves it.
* **Keep imported originals.** Files are stored untouched with a SHA-256 hash; a change is a new version, never an overwrite.
* **Record why** when you reject, waive or override anything. Reasons are kept in the audit trail.
* **Check Readiness before you submit.** Only registered human approvers, a production environment and no demo or synthetic data make an export submission ready.
* **Back up** before large imports (Settings, General).

## Don't
* **Don't approve your own work.** The four-eyes rule is enforced on the server; an Administrator is not exempt for assumptions, norms, profiles, baselines, queries, documents and rates.
* **Don't treat a missing rate as zero.** A missing rate stays missing and the line is unpriced.
* **Don't use index data (GASTAT CCI) as a price**, and don't apply regional multipliers.
* **Don't enter placeholder values to "get green".** Synthetic data is always labelled SYNTHETIC / DEMO / NOT A MARKET QUOTE and blocks a submission-ready export.
* **Don't put client files, secrets or the `var/` folder into version control.**
* **Don't rely on AI output.** AI can only propose; a person approves. It has no approval authority.
* **Don't claim compliance** with a standard or an owner's requirements; the register states what was read and what was not.
* **Don't share accounts.** Each approver needs their own login so the audit trail names a real person.

## Where things live
| You want to | Go to |
|---|---|
| Approve or reject pending items | Approvals |
| Bring in prices from Excel | Libraries, Rates workbook |
| Add or reset a user, check the audit trail, see hashes, read the rules | Settings |
| See what is blocking a tender | Project, Control tower |
