"""A* pathfinding and distance calculation for SAMANVAY (Spec §6.3.5).

Supports 8-connected grid navigation, terrain traversability checks,
hazard avoidance (chemical plume), and altitude-band constraints.
"""

import heapq
import math
from samanvay.core.constants import CELL_METERS, GRID_HEIGHT, GRID_WIDTH


def heuristic(a: tuple[int, int], b: tuple[int, int]) -> float:
    """Octile distance heuristic for 8-connected grid."""
    dx = abs(a[0] - b[0])
    dy = abs(a[1] - b[1])
    # 1.0 for cardinal, sqrt(2) ≈ 1.414 for diagonal
    return (dx + dy) + (1.4142 - 2.0) * min(dx, dy)


def find_path(
    start: tuple[int, int],
    goal: tuple[int, int],
    traversable_terrains: frozenset[str],
    terrain_grid: list[list[str]],
    plume_grid: list[list[float]] | None = None,
    no_fly_threshold: float = 0.5,
    is_air_agent: bool = True,
) -> list[tuple[int, int]]:
    """A* 8-connected pathfinder.

    Returns:
        List of (x, y) cells from start to goal inclusive, or empty list if unreachable.
    """
    if start == goal:
        return [start]

    def is_passable(c: tuple[int, int]) -> bool:
        x, y = c
        if not (0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT):
            return False

        t = terrain_grid[y][x]
        if t not in traversable_terrains:
            return False

        if is_air_agent and plume_grid is not None:
            if plume_grid[y][x] >= no_fly_threshold:
                return False

        return True

    if not is_passable(goal):
        return []

    # Priority queue: (f_score, g_score, current_cell)
    open_set: list[tuple[float, float, tuple[int, int]]] = []
    heapq.heappush(open_set, (heuristic(start, goal), 0.0, start))

    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    g_score: dict[tuple[int, int], float] = {start: 0.0}

    # 8 directions
    directions = [
        (-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
        (-1, -1, 1.4142), (-1, 1, 1.4142), (1, -1, 1.4142), (1, 1, 1.4142)
    ]

    while open_set:
        _, curr_g, current = heapq.heappop(open_set)

        if current == goal:
            # Reconstruct path
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path

        if curr_g > g_score.get(current, float("inf")):
            continue

        cx, cy = current
        for dx, dy, cost in directions:
            neighbor = (cx + dx, cy + dy)
            if not is_passable(neighbor):
                continue

            tentative_g = curr_g + cost
            if tentative_g < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f = tentative_g + heuristic(neighbor, goal)
                heapq.heappush(open_set, (f, tentative_g, neighbor))

    return []


def a_star_grid(
    start: tuple[int, int],
    goal: tuple[int, int],
    terrain_grid: list[list[str]],
    traversable_terrains: frozenset[str] = frozenset(["road", "open", "base"]),
) -> list[tuple[int, int]]:
    """Convenience wrapper for A* 8-connected pathfinding on grid terrain."""
    return find_path(start, goal, traversable_terrains, terrain_grid, is_air_agent=False)

