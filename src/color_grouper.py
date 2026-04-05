import math

from models import Color, Action


def group_colors(colors: set[Color], tolerance: int) -> dict[Color, list[Color]]:
    """Group similar colors by Euclidean RGB distance.

    Returns a dict mapping representative Color → list of member Colors.
    For tolerance=0 each color is its own group (zero overhead).
    For tolerance>0 uses greedy clustering: seed on the first unassigned color,
    collect all others within distance ≤ tolerance, compute centroid as
    representative, repeat until all colors are assigned.
    """
    if not colors:
        return {}
    if tolerance == 0:
        return {c: [c] for c in colors}

    unassigned = sorted(colors, key=lambda c: (c.r, c.g, c.b))
    groups: dict[Color, list[Color]] = {}

    while unassigned:
        seed = unassigned[0]
        members = [c for c in unassigned if _distance(seed, c) <= tolerance]
        for m in members:
            unassigned.remove(m)
        rep = _centroid(members)
        groups[rep] = members

    return groups


def find_group(sampled: Color, groups: dict[Color, list[Color]]) -> Color:
    """Return the representative whose group contains the member closest to sampled."""
    best_rep = None
    best_dist = float('inf')
    for rep, members in groups.items():
        for member in members:
            d = _distance(sampled, member)
            if d < best_dist:
                best_dist = d
                best_rep = rep
    return best_rep


def transfer_actions(
    old_groups: dict[Color, list[Color]],
    new_groups: dict[Color, list[Color]],
    old_actions: dict[Color, Action],
    default_action: Action,
) -> dict[Color, Action]:
    """Build a new actions dict for new_groups, preserving actions from old_groups.

    For each new representative, finds the old representative whose members have
    the most overlap with the new group. If no overlap exists, falls back to the
    closest old representative by Euclidean distance. Defaults to default_action
    when old_groups is empty.
    """
    member_to_old_rep: dict[Color, Color] = {
        m: rep for rep, members in old_groups.items() for m in members
    }

    new_actions: dict[Color, Action] = {}
    for new_rep, new_members in new_groups.items():
        overlap: dict[Color, int] = {}
        for m in new_members:
            if m in member_to_old_rep:
                old_rep = member_to_old_rep[m]
                overlap[old_rep] = overlap.get(old_rep, 0) + 1

        if overlap:
            best_old_rep = max(overlap, key=lambda r: overlap[r])
            new_actions[new_rep] = old_actions.get(best_old_rep, default_action)
        elif old_groups:
            closest_old_rep = min(old_groups, key=lambda r: _distance(new_rep, r))
            new_actions[new_rep] = old_actions.get(closest_old_rep, default_action)
        else:
            new_actions[new_rep] = default_action

    return new_actions


def expand_mapping(
    groups: dict[Color, list[Color]],
    actions: dict[Color, Action],
    default_action: Action,
) -> dict[Color, Action]:
    """Expand representative→action to member→action for every member in every group."""
    return {
        member: actions.get(rep, default_action)
        for rep, members in groups.items()
        for member in members
    }


def _distance(a: Color, b: Color) -> float:
    return math.sqrt((a.r - b.r) ** 2 + (a.g - b.g) ** 2 + (a.b - b.b) ** 2)


def _centroid(colors: list[Color]) -> Color:
    n = len(colors)
    return Color(
        round(sum(c.r for c in colors) / n),
        round(sum(c.g for c in colors) / n),
        round(sum(c.b for c in colors) / n),
    )
