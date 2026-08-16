"""Typosquat detection: Levenshtein distance against a seed list of popular packages."""

from __future__ import annotations

from typing import Optional

POPULAR_PACKAGES = [
    "react",
    "lodash",
    "express",
    "axios",
    "vue",
    "angular",
    "webpack",
    "babel",
    "typescript",
    "eslint",
    "jest",
    "mocha",
    "chalk",
    "commander",
    "moment",
    "request",
    "async",
    "underscore",
    "jquery",
    "bootstrap",
    "next",
    "nuxt",
    "redux",
    "rxjs",
    "socket.io",
    "prettier",
    "dotenv",
    "uuid",
    "yargs",
    "node-sass",
    "sass",
    "postcss",
    "vite",
    "electron",
    "puppeteer",
]


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if len(a) == 0:
        return len(b)
    if len(b) == 0:
        return len(a)

    previous_row = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current_row = [i]
        for j, char_b in enumerate(b, start=1):
            insert_cost = current_row[j - 1] + 1
            delete_cost = previous_row[j] + 1
            substitute_cost = previous_row[j - 1] + (char_a != char_b)
            current_row.append(min(insert_cost, delete_cost, substitute_cost))
        previous_row = current_row

    return previous_row[-1]


def closest_popular_match(package_name: str, max_distance: int = 2) -> Optional[tuple[str, int]]:
    """Return (popular_name, distance) for the closest popular package within
    max_distance, or None if the name is an exact match or no close match exists."""
    name = package_name.lower()
    best: Optional[tuple[str, int]] = None

    for popular in POPULAR_PACKAGES:
        if name == popular:
            return None
        distance = levenshtein(name, popular)
        if distance <= max_distance and (best is None or distance < best[1]):
            best = (popular, distance)

    return best
