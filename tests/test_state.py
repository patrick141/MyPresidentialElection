"""
Unit tests for the State class.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.model.state import State


def test_state_instantiation():
    # Verify a State object can be created with basic arguments
    s = State("Pennsylvania", 19)
    assert s.get_name() == "Pennsylvania"
    assert s.get_ev() == 19


if __name__ == "__main__":
    test_state_instantiation()
    print("test_state_instantiation passed")
