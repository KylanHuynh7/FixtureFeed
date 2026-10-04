"""Property-based tests (DECISIONS.md #6): invariants of the diff logic over
random sequences of snapshots, not just hand-picked examples."""

from datetime import datetime, timedelta, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from fixturefeed.diff import content_hash
from fixturefeed.models import SourceGame
from tests.test_diff import Store

TEAMS = ["BUF", "DAL", "KC", "SF"]
# Every ordered home/away pair is one possible game, with a fixed ESPN ID.
PAIRS = [(h, a) for h in TEAMS for a in TEAMS if h != a]
BASE = datetime(2026, 9, 13, 17, 0, tzinfo=timezone.utc)

game_state = st.fixed_dictionaries({
    "week": st.integers(1, 18),
    "hours": st.integers(0, 24 * 120),
    "tbd": st.booleans(),
    "venue": st.sampled_from(["Stadium A", "Stadium B", None]),
})
# A snapshot: some subset of the possible games, each in some state.
snapshot = st.dictionaries(st.sampled_from(range(len(PAIRS))), game_state, min_size=1)


def to_source(i, s):
    home, away = PAIRS[i]
    return SourceGame(
        season=2026, game_type="REG", week=s["week"], home_team=home, away_team=away,
        start_utc=BASE + timedelta(hours=s["hours"]), time_tbd=s["tbd"], venue=s["venue"],
        source_ids={"espn": str(1000 + i), "game_id": f"2026_{s['week']:02d}_{away}_{home}"},
    )


@settings(max_examples=300, deadline=None)
@given(st.lists(snapshot, min_size=1, max_size=8))
def test_invariants_over_snapshot_sequences(snapshots):
    store = Store()
    uid_for_key = {}

    for snap in snapshots:
        before = dict(store.games)
        incoming = [to_source(i, s) for i, s in snap.items()]
        store.sync(incoming)
        present = {g.natural_key for g in incoming}

        # One stored game per real game, ever: no duplicates.
        keys = [g.natural_key for g in store.games.values()]
        assert len(keys) == len(set(keys))

        for g in store.games.values():
            # A game's UID never changes.
            assert uid_for_key.setdefault(g.natural_key, g.ics_uid) == g.ics_uid
            # Status mirrors presence in the latest snapshot.
            assert g.status == ("scheduled" if g.natural_key in present else "cancelled")
            # Stored hash always matches stored content.
            assert g.content_hash == content_hash(g)

            old = before.get(g.id)
            if old is not None:
                # SEQUENCE never decreases, and moves exactly when visible content does.
                assert g.sequence >= old.sequence
                assert (g.sequence > old.sequence) == (g.content_hash != old.content_hash)
                assert g.sequence - old.sequence <= 1

        # Present games match the source exactly.
        for src in incoming:
            g = next(x for x in store.games.values() if x.natural_key == src.natural_key)
            assert (g.week, g.start_utc, g.time_tbd, g.venue) == (
                src.week, src.start_utc, src.time_tbd, src.venue)

        # Applying the same snapshot again is a no-op.
        assert store.sync(incoming).diffs == []
