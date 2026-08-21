"""Typosquat detection: Levenshtein distance against a seed list of popular
packages, per ecosystem - npm's "react"/"lodash" mean nothing as a typosquat
anchor for a PyPI or Maven scan, so each ecosystem gets its own seed list
rather than sharing npm's."""

from __future__ import annotations

from typing import Optional

from app.models.schemas import Ecosystem

POPULAR_PACKAGES_NPM = [
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

POPULAR_PACKAGES_PYPI = [
    "requests",
    "numpy",
    "pandas",
    "flask",
    "django",
    "pytest",
    "boto3",
    "urllib3",
    "click",
    "pyyaml",
    "setuptools",
    "wheel",
    "six",
    "certifi",
    "charset-normalizer",
    "idna",
    "pillow",
    "cryptography",
    "sqlalchemy",
    "jinja2",
    "markupsafe",
    "protobuf",
    "grpcio",
    "scipy",
    "matplotlib",
]

POPULAR_PACKAGES_MAVEN = [
    "com.google.guava:guava",
    "org.springframework:spring-core",
    "org.springframework.boot:spring-boot-starter",
    "junit:junit",
    "org.junit.jupiter:junit-jupiter",
    "com.fasterxml.jackson.core:jackson-databind",
    "org.apache.commons:commons-lang3",
    "commons-io:commons-io",
    "org.slf4j:slf4j-api",
    "ch.qos.logback:logback-classic",
    "org.hibernate:hibernate-core",
    "com.google.code.gson:gson",
    "org.mockito:mockito-core",
    "org.apache.httpcomponents:httpclient",
    "io.netty:netty-all",
    "org.projectlombok:lombok",
    "com.squareup.okhttp3:okhttp",
    "com.squareup.retrofit2:retrofit",
    "org.apache.logging.log4j:log4j-core",
    "mysql:mysql-connector-java",
]

_POPULAR_PACKAGES_BY_ECOSYSTEM: dict[Ecosystem, list[str]] = {
    "npm": POPULAR_PACKAGES_NPM,
    "pypi": POPULAR_PACKAGES_PYPI,
    "maven": POPULAR_PACKAGES_MAVEN,
}


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


def closest_popular_match(
    package_name: str, ecosystem: Ecosystem = "npm", max_distance: int = 2
) -> Optional[tuple[str, int]]:
    """Return (popular_name, distance) for the closest popular package within
    max_distance, or None if the name is an exact match or no close match exists."""
    name = package_name.lower()
    best: Optional[tuple[str, int]] = None

    for popular in _POPULAR_PACKAGES_BY_ECOSYSTEM.get(ecosystem, POPULAR_PACKAGES_NPM):
        if name == popular:
            return None
        distance = levenshtein(name, popular)
        if distance <= max_distance and (best is None or distance < best[1]):
            best = (popular, distance)

    return best
