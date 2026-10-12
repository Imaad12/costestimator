from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Actor:
    """The authenticated principal performing an action. Permissions are always checked server-side."""

    username: str
    role: str
    display_name: str = ""
    is_ai: bool = False

    @property
    def label(self) -> str:
        return f"{self.username} ({self.role})"


SYSTEM_SEED = Actor(username="system:seed", role="Administrator", display_name="Demo/Reference data seeder")
