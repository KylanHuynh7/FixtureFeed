"""Source-independent game records shared by adapters, matcher, and feed."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class SourceGame:
    """One game as a source reports it right now. Not yet matched to our IDs."""

    season: int
    game_type: str
    week: int
    home_team: str
    away_team: str
    start_utc: datetime  # timezone-aware, UTC
    time_tbd: bool
    venue: str | None
    # id_kind -> external ID, e.g. {"game_id": "2026_04_PIT_CLE", "espn": "401872964"}
    source_ids: dict[str, str] = field(default_factory=dict, hash=False, compare=False)

    @property
    def natural_key(self) -> tuple[int, str, str, str]:
        # NFL-only: unique per season (DECISIONS.md #18). Other sports need date/game number.
        return (self.season, self.game_type, self.home_team, self.away_team)
