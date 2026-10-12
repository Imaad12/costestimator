"""Rate-update pipeline: manifests, candidate review queue, normalisation, publication (docs/RATE_UPDATE_WORKFLOW.md).

Everything here creates *proposals*. Only a human decision (approvals.engine) can make a candidate publishable, and only a second
human rate approval (services.rates.approve_rate) makes the published version eligible for a submission-ready estimate."""
