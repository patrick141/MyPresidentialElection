"""
Unit tests for the Election class.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.model.election import Election


def test_election_instantiation():
    # Verify an Election object loads successfully from the 2024 CSV
    e = Election("2024")
    assert e.year == "2024"
    assert len(e.states) > 0


if __name__ == "__main__":
    test_election_instantiation()
    print("test_election_instantiation passed")
