"""Match a new snapshot to stored games and plan the changes (DECISIONS.md #18).

Pure functions: no database or network. The persistence layer loads stored
games, calls `validate_snapshot` and `plan_changes`, then writes the plan.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Callable, Literal

from fixturefeed.config import ICS_UID_SUFFIX
from fixturefeed.models import SourceGame

# Fields a calendar shows. A change here bumps SEQUENCE (#18 D).
VISIBLE_FIELDS = ("home_team", "away_team", "start_utc", "time_tbd", "venue", "status")
# Also recorded in the change log, but invisible in the calendar, so no bump.
TRACKED_FIELDS = VISIBLE_FIELDS + ("week",)

# Reject a snapshot whose season shrinks by more than this fraction (#18 B).
MAX_ROW_DROP = 0.05


@dataclass(frozen=True)
class StoredGame:
    """A game as it currently exists in our database."""

    id: uuid.UUID
    ics_uid: str
    season: int
    game_type: str
    week: int
    home_team: str
    away_team: str
    start_utc: datetime
    time_tbd: bool
    venue: str | None
    status: Literal["scheduled", "cancelled"]
    sequence: int
    content_hash: str

    @property
    def natural_key(self) -> tuple[int, str, str, str]:
        return (self.season, self.game_type, self.home_team, self.away_team)


@dataclass(frozen=True)
class FieldChange:
    field: str
    old: str | None
    new: str | None


@dataclass(frozen=True)
class GameDiff:
    """The new state of one game plus what changed to get there."""

    game: StoredGame
    change_type: Literal["created", "updated", "cancelled", "restored"]
    field_changes: tuple[FieldChange, ...] = ()


@dataclass
class ChangePlan:
    diffs: list[GameDiff] = field(default_factory=list)
    # (game id, id_kind, external_id) for every game in the snapshot, so newly
    # assigned source IDs (e.g. gsis after kickoff) get recorded.
    source_ids: list[tuple[uuid.UUID, str, str]] = field(default_factory=list)


class MatchConflict(Exception):
    """The snapshot maps onto stored games ambiguously; don't guess."""


def content_hash(game: StoredGame) -> str:
    visible = {f: _fmt(getattr(game, f)) for f in VISIBLE_FIELDS}
    return hashlib.sha256(json.dumps(visible, sort_keys=True).encode()).hexdigest()


def validate_snapshot(
    incoming: list[SourceGame],
    stored: list[StoredGame],
    previous_row_count: int | None,
) -> str | None:
    """Return a reject reason, or None if the snapshot looks trustworthy."""
    if not incoming:
        return "snapshot has no games for this season"

    keys = [g.natural_key for g in incoming]
    if len(keys) != len(set(keys)):
        return "snapshot has duplicate games (same season, type, home, away)"

    espn = [g.source_ids["espn"] for g in incoming if "espn" in g.source_ids]
    if len(espn) != len(set(espn)):
        return "snapshot has duplicate ESPN IDs"

    if previous_row_count and len(incoming) < previous_row_count * (1 - MAX_ROW_DROP):
        return f"row count dropped from {previous_row_count} to {len(incoming)}"

    teams_before = {t for g in stored if g.status == "scheduled"
                    for t in (g.home_team, g.away_team)}
    teams_now = {t for g in incoming for t in (g.home_team, g.away_team)}
    if missing := sorted(teams_before - teams_now):
        return f"teams with no games: {', '.join(missing)}"

    return None


def plan_changes(
    stored: list[StoredGame],
    incoming: list[SourceGame],
    espn_index: dict[str, uuid.UUID],
    new_id: Callable[[], uuid.UUID] = uuid.uuid4,
) -> ChangePlan:
    """Work out creates, updates, cancellations, and restorations.

    `espn_index` maps every ESPN ID we have ever recorded to our game ID.
    Raises MatchConflict instead of guessing when the two keys disagree.
    """
    by_key = {g.natural_key: g for g in stored}
    by_id = {g.id: g for g in stored}
    plan = ChangePlan()
    matched: set[uuid.UUID] = set()

    for src in incoming:
        current = _match(src, by_key, by_id, espn_index)
        if current is not None:
            if current.id in matched:
                raise MatchConflict(f"two snapshot rows match game {current.id}")
            matched.add(current.id)
            diff = _diff_existing(current, src)
            if diff:
                plan.diffs.append(diff)
            game_id = current.id
        else:
            created = _create(src, new_id())
            plan.diffs.append(GameDiff(created, "created"))
            game_id = created.id
        plan.source_ids += [(game_id, k, v) for k, v in src.source_ids.items()]

    # Anything scheduled that the source no longer lists is treated as cancelled.
    for g in stored:
        if g.id not in matched and g.status == "scheduled":
            cancelled = _with_hash(replace(g, status="cancelled", sequence=g.sequence + 1))
            plan.diffs.append(GameDiff(cancelled, "cancelled",
                                       (FieldChange("status", "scheduled", "cancelled"),)))
    return plan


def _match(src, by_key, by_id, espn_index) -> StoredGame | None:
    via_key = by_key.get(src.natural_key)
    espn_game_id = espn_index.get(src.source_ids.get("espn", ""))
    via_espn = by_id.get(espn_game_id) if espn_game_id else None
    if via_key and via_espn and via_key.id != via_espn.id:
        raise MatchConflict(
            f"{src.source_ids.get('game_id')}: natural key matches {via_key.id}, "
            f"ESPN ID matches {via_espn.id}"
        )
    return via_key or via_espn


def _diff_existing(current: StoredGame, src: SourceGame) -> GameDiff | None:
    updated = replace(
        current, week=src.week, home_team=src.home_team, away_team=src.away_team,
        start_utc=src.start_utc, time_tbd=src.time_tbd, venue=src.venue,
        status="scheduled",
    )
    changes = tuple(
        FieldChange(f, _fmt(getattr(current, f)), _fmt(getattr(updated, f)))
        for f in TRACKED_FIELDS
        if getattr(current, f) != getattr(updated, f)
    )
    if not changes:
        return None

    new_hash = content_hash(updated)
    if new_hash != current.content_hash:
        updated = replace(updated, sequence=current.sequence + 1)
    updated = replace(updated, content_hash=new_hash)

    change_type = "restored" if current.status == "cancelled" else "updated"
    # The status flip is implied by "restored"; log only the other fields.
    changes = tuple(c for c in changes if c.field != "status")
    return GameDiff(updated, change_type, changes)


def _create(src: SourceGame, game_id: uuid.UUID) -> StoredGame:
    return _with_hash(StoredGame(
        id=game_id, ics_uid=f"{game_id}@{ICS_UID_SUFFIX}",
        season=src.season, game_type=src.game_type, week=src.week,
        home_team=src.home_team, away_team=src.away_team,
        start_utc=src.start_utc, time_tbd=src.time_tbd, venue=src.venue,
        status="scheduled", sequence=0, content_hash="",
    ))


def _with_hash(game: StoredGame) -> StoredGame:
    return replace(game, content_hash=content_hash(game))


def _fmt(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        # Normalize: the same instant read back from Postgres may carry the
        # session's offset, which must not look like a change.
        return value.astimezone(timezone.utc).isoformat()
    return str(value)
