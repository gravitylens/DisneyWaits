from datetime import UTC, datetime, timedelta
import os, sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from disneywaits.stats import RideStats


def test_ride_stats_mean_std_and_unusual():
    stats = RideStats()
    now = datetime.now(UTC)
    for i in range(5):
        stats.add_wait(10 + i, now - timedelta(minutes=5 * i))
    assert round(stats.mean(), 2) == 12.0
    assert round(stats.stdev(), 2) > 0
    stats.add_wait(1, now + timedelta(minutes=5))
    assert stats.is_unusually_low()


def test_ride_stats_trim_history():
    stats = RideStats()
    old = datetime.now(UTC) - timedelta(days=6)
    stats.add_wait(10, old)
    stats.add_wait(20)
    assert len(stats.history) == 1


def test_recently_opened_flag():
    stats = RideStats()
    stats.mark_closed()
    stats.mark_open()
    assert stats.recently_opened is True
    stats.mark_open()
    assert stats.recently_opened is False
