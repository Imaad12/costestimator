"""Provider-independent public-source access (docs/RATE_UPDATE_WORKFLOW.md).

Nothing in the core estimating path imports this package: estimates are calculated entirely from the local database.
Each provider is isolated, so a blocked source never affects another one or the application."""
