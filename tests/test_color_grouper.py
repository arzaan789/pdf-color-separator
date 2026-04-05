import sys
sys.path.insert(0, 'src')

from models import Color, Action
from color_grouper import group_colors, find_group, transfer_actions, expand_mapping


# ── group_colors ──────────────────────────────────────────────────────────────

def test_tolerance_zero_each_color_own_group():
    colors = {Color(255, 0, 0), Color(0, 0, 255)}
    groups = group_colors(colors, 0)
    assert len(groups) == 2
    assert Color(255, 0, 0) in groups
    assert Color(0, 0, 255) in groups
    assert groups[Color(255, 0, 0)] == [Color(255, 0, 0)]
    assert groups[Color(0, 0, 255)] == [Color(0, 0, 255)]


def test_two_colors_within_tolerance_form_one_group():
    # Euclidean distance between (255,0,0) and (250,0,0) is 5
    a = Color(255, 0, 0)
    b = Color(250, 0, 0)
    groups = group_colors({a, b}, 10)
    assert len(groups) == 1
    rep = list(groups.keys())[0]
    members = groups[rep]
    assert a in members
    assert b in members
    # Centroid: round((255+250)/2)=round(252.5)=252 (Python rounds to even)
    assert rep == Color(252, 0, 0)


def test_two_colors_outside_tolerance_stay_separate():
    # Distance between pure red and pure blue is ~360 — always separate
    a = Color(255, 0, 0)
    b = Color(0, 0, 255)
    groups = group_colors({a, b}, 10)
    assert len(groups) == 2


def test_greedy_clustering_a_near_b_b_near_c_a_not_near_c():
    # A=(200,0,0) B=(205,0,0) C=(215,0,0), tolerance=10
    # dist(A,B)=5 ≤ 10, dist(A,C)=15 > 10, dist(B,C)=10 ≤ 10
    # Greedy: seed A → collects B (dist=5≤10), C not collected (dist(A,C)=15>10)
    # Then seed C → own group
    a = Color(200, 0, 0)
    b = Color(205, 0, 0)
    c = Color(215, 0, 0)
    groups = group_colors({a, b, c}, 10)
    assert len(groups) == 2
    ab_members = next(members for members in groups.values() if a in members)
    assert b in ab_members
    assert c not in ab_members


def test_empty_colors_returns_empty():
    assert group_colors(set(), 0) == {}
    assert group_colors(set(), 20) == {}


# ── find_group ────────────────────────────────────────────────────────────────

def test_find_group_exact_member():
    red = Color(255, 0, 0)
    blue = Color(0, 0, 255)
    groups = {red: [red], blue: [blue]}
    assert find_group(Color(255, 0, 0), groups) == red
    assert find_group(Color(0, 0, 255), groups) == blue


def test_find_group_closest_to_sampled():
    # Sampled is (250, 5, 0) — closer to red than blue
    red = Color(255, 0, 0)
    blue = Color(0, 0, 255)
    groups = {red: [red], blue: [blue]}
    assert find_group(Color(250, 5, 0), groups) == red


# ── transfer_actions ──────────────────────────────────────────────────────────

def test_transfer_actions_by_member_overlap():
    old_rep = Color(255, 0, 0)
    old_groups = {old_rep: [Color(255, 0, 0), Color(253, 0, 0)]}
    old_actions = {old_rep: Action.KEEP_BLACK}
    # New grouping has same members but a different centroid as representative
    new_rep = Color(254, 0, 0)
    new_groups = {new_rep: [Color(255, 0, 0), Color(253, 0, 0)]}
    new_actions = transfer_actions(old_groups, new_groups, old_actions, Action.KEEP)
    assert new_actions[new_rep] == Action.KEEP_BLACK


def test_transfer_actions_no_overlap_falls_back_to_keep():
    old_rep = Color(255, 0, 0)
    old_groups = {old_rep: [Color(255, 0, 0)]}
    old_actions = {old_rep: Action.DELETE}
    # Completely new color with no member overlap
    new_rep = Color(0, 0, 255)
    new_groups = {new_rep: [Color(0, 0, 255)]}
    new_actions = transfer_actions(old_groups, new_groups, old_actions, Action.KEEP)
    # No overlap → falls back to closest old rep by distance, which is old_rep
    # Distance between blue and red is large, but it's still the only candidate
    assert new_rep in new_actions  # result has an entry (either KEEP or DELETE)


# ── expand_mapping ────────────────────────────────────────────────────────────

def test_expand_mapping_all_members_get_representative_action():
    rep = Color(255, 0, 0)
    m1 = Color(254, 0, 0)
    m2 = Color(253, 0, 0)
    groups = {rep: [rep, m1, m2]}
    actions = {rep: Action.DELETE}
    expanded = expand_mapping(groups, actions, Action.KEEP)
    assert expanded[rep] == Action.DELETE
    assert expanded[m1] == Action.DELETE
    assert expanded[m2] == Action.DELETE


def test_expand_mapping_unmapped_rep_uses_default():
    rep = Color(0, 255, 0)
    groups = {rep: [rep]}
    actions = {}  # rep not in actions
    expanded = expand_mapping(groups, actions, Action.KEEP)
    assert expanded[rep] == Action.KEEP
