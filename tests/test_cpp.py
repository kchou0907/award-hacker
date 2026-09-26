from datetime import datetime, timezone

from c1_awards.capital_one import capital_one_miles_needed, effective_cpp


def test_one_to_one():
    assert capital_one_miles_needed(75_000, 1.0) == 75_000
    assert round(effective_cpp(2500, 80, 75_000), 3) == 3.227


def test_eva_ratio():
    assert capital_one_miles_needed(75_000, 0.75) == 100_000
    assert round(effective_cpp(2500, 80, 100_000), 3) == 2.420


def test_transfer_bonus():
    assert capital_one_miles_needed(75_000, 1.0, 0.20) == 62_500
    assert round(effective_cpp(2500, 80, 62_500), 3) == 3.872


def test_minimum_transfer():
    assert capital_one_miles_needed(500, 1.0) == 1_000
