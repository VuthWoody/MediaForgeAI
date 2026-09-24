"""Hungarian (Kuhn-Munkres) Bipartite Matching Algorithm.

Used in VoxReel §10.2 to solve optimal one-to-one assignment of audio clusters
to registered actor profiles, preventing cluster collision.
Includes pure NumPy/Python Kuhn-Munkres implementation with optional SciPy acceleration.
"""

from __future__ import annotations

import numpy as np


def _kuhn_munkres(cost_matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Solve the linear sum assignment problem minimizing sum of costs.

    Pure NumPy/Python implementation of the O(n^3) Hungarian algorithm.
    """
    cost = np.array(cost_matrix, dtype=float)
    transposed = False
    n_rows, n_cols = cost.shape
    if n_rows > n_cols:
        cost = cost.T
        transposed = True
        n_rows, n_cols = cost.shape

    u = np.zeros(n_rows)
    v = np.zeros(n_cols)
    p = np.zeros(n_cols, dtype=int)
    way = np.zeros(n_cols, dtype=int)

    for i in range(1, n_rows + 1):
        p[0] = i
        j0 = 0
        minv = np.full(n_cols, np.inf)
        used = np.zeros(n_cols, dtype=bool)

        while True:
            used[j0] = True
            i0 = p[j0]
            delta = np.inf
            j1 = 0

            for j in range(1, n_cols):
                if not used[j]:
                    cur = cost[i0 - 1, j] - u[i0 - 1] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j

            for j in range(n_cols):
                if used[j]:
                    u[p[j] - 1] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta

            j0 = j1
            if p[j0] == 0:
                break

        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break

    row_ind = np.zeros(n_rows, dtype=int)
    col_ind = np.zeros(n_rows, dtype=int)
    for j in range(1, n_cols):
        if p[j] > 0 and p[j] <= n_rows:
            row_ind[p[j] - 1] = p[j] - 1
            col_ind[p[j] - 1] = j

    if transposed:
        return col_ind, row_ind
    return row_ind, col_ind


def linear_sum_assignment(cost_matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Find row and column indices that minimize the total cost.

    Falls back from scipy.optimize.linear_sum_assignment to pure Python implementation.
    """
    cost = np.asarray(cost_matrix, dtype=float)
    if cost.size == 0:
        return np.array([], dtype=int), np.array([], dtype=int)

    try:
        import scipy.optimize  # type: ignore[import-untyped]
        r, c = scipy.optimize.linear_sum_assignment(cost)
        return np.asarray(r, dtype=int), np.asarray(c, dtype=int)
    except (ImportError, AttributeError):
        pass

    # Pad cost matrix to have 1-based indexing for Kuhn-Munkres
    n_rows, n_cols = cost.shape
    # Add dummy col 0 and row 0 for standard Kuhn-Munkres implementation
    padded = np.zeros((n_rows, n_cols + 1), dtype=float)
    padded[:, 1:] = cost

    row_ind, col_ind = _kuhn_munkres(padded)
    # Adjust 1-based col_ind back to 0-based
    col_ind = col_ind - 1
    return row_ind, col_ind


def match_clusters_to_candidates(
    similarity_matrix: np.ndarray,
) -> list[tuple[int, int, float]]:
    """Perform maximum-weight bipartite matching on a similarity matrix.

    Args:
        similarity_matrix: 2D array of shape (num_clusters, num_candidates)
                           where values represent similarity in [0.0, 1.0].

    Returns:
        List of tuples: (cluster_index, candidate_index, similarity_score).
    """
    sim = np.asarray(similarity_matrix, dtype=float)
    if sim.size == 0 or sim.shape[0] == 0 or sim.shape[1] == 0:
        return []

    # Kuhn-Munkres minimizes cost, so convert similarities to costs:
    # cost = max(sim) - sim
    max_val = np.max(sim) if np.max(sim) > 0 else 1.0
    cost_matrix = max_val - sim

    row_ind, col_ind = linear_sum_assignment(cost_matrix)

    matches: list[tuple[int, int, float]] = []
    for r, c in zip(row_ind, col_ind, strict=False):
        matches.append((int(r), int(c), float(sim[r, c])))

    # Sort matches by cluster index
    matches.sort(key=lambda m: m[0])
    return matches
