"""Pure string utility functions.

Shared across the engine (loader, condition evaluator, TUI) to avoid
duplicating common string operations. All functions are pure Python with
no external dependencies beyond the standard library.
"""

from __future__ import annotations


def levenshtein(a: str, b: str) -> int:
    """Compute the Levenshtein (edit) distance between two strings.

    Uses a two-row DP approach: O(m×n) time, O(n) space.
    Useful for typo detection — a distance of 1 covers single-character
    substitutions, insertions, or deletions (e.g. 'legendery' → 'legendary').
    """
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            dp[j] = prev if a[i - 1] == b[j - 1] else 1 + min(prev, dp[j], dp[j - 1])
            prev = temp
    return dp[n]
