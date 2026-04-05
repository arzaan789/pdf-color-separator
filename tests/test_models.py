import sys
sys.path.insert(0, 'src')

from models import Color, Action


def test_color_equality():
    assert Color(255, 0, 0) == Color(255, 0, 0)


def test_color_inequality():
    assert Color(255, 0, 0) != Color(0, 0, 255)


def test_color_hashable_for_set():
    s = {Color(255, 0, 0), Color(0, 0, 255), Color(255, 0, 0)}
    assert len(s) == 2


def test_color_str():
    assert str(Color(255, 0, 0)) == "#ff0000"
    assert str(Color(0, 255, 0)) == "#00ff00"
    assert str(Color(0, 0, 0)) == "#000000"


def test_action_values():
    assert Action.KEEP != Action.KEEP_BLACK
    assert Action.KEEP_BLACK != Action.DELETE
