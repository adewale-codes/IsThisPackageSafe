"""Phase 9: manifest parsing.

Parses the *contents* of manifest files (never reads from a server-side
path - the CLI reads local files and uploads their text, see
routers/repo.py) into a flat list of DependencySpec per ecosystem. This
module only extracts "what does this manifest declare" - concrete version
resolution (range -> exact) lives in version_resolve.py, and the actual
scanning lives in repo_scan.py.
"""

from __future__ import annotations

import re
import tomllib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional

from app.models.schemas import Ecosystem

# How a DependencySpec's version was determined - carried through to the
# final report so a user can tell "we know this for certain" (lockfile/
# exact-pin) apart from "we picked the latest version satisfying a range"
# (a meaningfully less certain claim about what's actually installed).
ResolutionMethod = str  # "lockfile" | "exact" | "range" | "unresolved"


@dataclass
class DependencySpec:
    ecosystem: Ecosystem
    name: str
    version_constraint: Optional[str]  # exact version, a range, or None (unconstrained)
    resolution_method: ResolutionMethod
    manifest_path: str
    dev: bool = False


_POM_NS = "{http://maven.apache.org/POM/4.0.0}"


def _pom_find(element: ET.Element, path: str) -> Optional[ET.Element]:
    namespaced = "/".join(f"{_POM_NS}{part}" for part in path.split("/"))
    found = element.find(namespaced)
    return found if found is not None else element.find(path)


def _pom_findall(element: ET.Element, path: str) -> list[ET.Element]:
    namespaced = "/".join(f"{_POM_NS}{part}" for part in path.split("/"))
    found = element.findall(namespaced)
    return found if found else element.findall(path)


def _pom_text(element: ET.Element, path: str) -> Optional[str]:
    found = _pom_find(element, path)
    if found is None or found.text is None:
        return None
    text = " ".join(found.text.split())
    return text or None


# ---------------------------------------------------------------------------
# npm: package.json (+ optional package-lock.json / yarn.lock)
# ---------------------------------------------------------------------------


def parse_package_json(content: str, manifest_path: str) -> list[DependencySpec]:
    import json

    data = json.loads(content)
    specs: list[DependencySpec] = []
    for section, is_dev in (("dependencies", False), ("devDependencies", True)):
        for name, range_spec in (data.get(section) or {}).items():
            if not isinstance(range_spec, str):
                continue
            # workspace:/file:/link:/git+... protocol specs point at local
            # or non-registry sources - nothing a registry client can scan.
            if re.match(r"^(workspace|file|link|git|github|https?):", range_spec.strip()):
                continue
            specs.append(
                DependencySpec(
                    ecosystem="npm",
                    name=name,
                    version_constraint=range_spec,
                    resolution_method="range",
                    manifest_path=manifest_path,
                    dev=is_dev,
                )
            )
    return specs


def resolve_npm_lockfile_versions(content: str, names: set[str]) -> dict[str, str]:
    """package-lock.json (v1-v3). v2/v3 use a flat `packages` map keyed by
    "node_modules/<name>" (or nested paths for de-duped sub-deps - only the
    top-level entry matters for pinning a manifest's own direct deps); v1
    uses a `dependencies` map keyed by bare name. Returns {name: exact_version}
    for whichever of `names` it can resolve - callers fall back to range
    resolution for any name not present here."""
    import json

    data = json.loads(content)
    resolved: dict[str, str] = {}

    packages = data.get("packages")
    if isinstance(packages, dict):
        for name in names:
            entry = packages.get(f"node_modules/{name}")
            if isinstance(entry, dict) and isinstance(entry.get("version"), str):
                resolved[name] = entry["version"]
        if resolved:
            return resolved

    dependencies = data.get("dependencies")
    if isinstance(dependencies, dict):
        for name in names:
            entry = dependencies.get(name)
            if isinstance(entry, dict) and isinstance(entry.get("version"), str):
                resolved[name] = entry["version"]

    return resolved


# Yarn classic (v1) lockfile: repeated blocks like
#   lodash@^4.17.0, lodash@^4.17.21:
#     version "4.17.21"
#     ...
# A block's header may list several comma-separated "name@range" specs, all
# resolving to the one version below. Yarn Berry (v2+) uses a different
# header syntax ("pkg@npm:^1.0.0":) and isn't parsed here - a range-based
# fallback is used for those instead of failing the whole scan.
_YARN_HEADER_RE = re.compile(r'^"?([^@"][^@]*)@([^,"]+)"?')
_YARN_VERSION_RE = re.compile(r'^\s+version\s+"([^"]+)"')


def resolve_yarn_lock_versions(content: str, names: set[str]) -> dict[str, str]:
    resolved: dict[str, str] = {}
    pending_names: set[str] = set()

    for line in content.splitlines():
        if line and not line[0].isspace() and line.rstrip().endswith(":"):
            pending_names = set()
            header = line.rstrip()[:-1]
            for spec in header.split(", "):
                match = _YARN_HEADER_RE.match(spec.strip())
                if match and match.group(1) in names:
                    pending_names.add(match.group(1))
            continue

        if pending_names:
            match = _YARN_VERSION_RE.match(line)
            if match:
                for name in pending_names:
                    resolved.setdefault(name, match.group(1))
                pending_names = set()

    return resolved


# ---------------------------------------------------------------------------
# Python: requirements.txt
# ---------------------------------------------------------------------------

# name, then an optional PEP 440 specifier (==, >=, <=, ~=, !=, >, <) chain.
_REQ_LINE_RE = re.compile(
    r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*((?:[=<>!~]=?[^,;#\s]*\s*,?\s*)*)"
)


def parse_requirements_txt(content: str, manifest_path: str) -> list[DependencySpec]:
    specs: list[DependencySpec] = []
    for raw_line in content.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("-") or line.startswith("--"):
            # -r other.txt / -e ./local / --index-url ... - not a resolvable
            # package reference, skip rather than mis-parse.
            continue
        # Drop an environment marker (e.g. "; python_version >= '3.8'") -
        # unrelated to which version to scan.
        line = line.split(";", 1)[0].strip()
        match = _REQ_LINE_RE.match(line)
        if not match:
            continue
        name = match.group(1)
        constraint = match.group(3).strip().rstrip(",") or None
        is_exact = bool(constraint) and constraint.startswith("==") and "," not in constraint
        specs.append(
            DependencySpec(
                ecosystem="pypi",
                name=name,
                version_constraint=(constraint[2:].strip() if is_exact else constraint),
                resolution_method="exact" if is_exact else ("range" if constraint else "unresolved"),
                manifest_path=manifest_path,
            )
        )
    return specs


# ---------------------------------------------------------------------------
# Python: pyproject.toml - both PEP 621 ([project.dependencies]) and Poetry
# ([tool.poetry.dependencies]) are supported, since neither is rare in the
# wild and the parsing cost of supporting both is small.
# ---------------------------------------------------------------------------

_PEP508_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*(.*)$")


def _parse_pep508(entry: str) -> Optional[tuple[str, Optional[str]]]:
    entry = entry.split(";", 1)[0].strip()  # drop environment marker
    match = _PEP508_NAME_RE.match(entry)
    if not match:
        return None
    name = match.group(1)
    constraint = match.group(3).strip() or None
    return name, constraint


def parse_pyproject_toml(content: str, manifest_path: str) -> list[DependencySpec]:
    data = tomllib.loads(content)
    specs: list[DependencySpec] = []

    project_deps = ((data.get("project") or {}).get("dependencies")) or []
    for entry in project_deps:
        if not isinstance(entry, str):
            continue
        parsed = _parse_pep508(entry)
        if not parsed:
            continue
        name, constraint = parsed
        specs.append(
            DependencySpec(
                ecosystem="pypi",
                name=name,
                version_constraint=constraint,
                resolution_method="range" if constraint else "unresolved",
                manifest_path=manifest_path,
            )
        )

    optional_deps = ((data.get("project") or {}).get("optional-dependencies")) or {}
    for group_deps in optional_deps.values():
        for entry in group_deps if isinstance(group_deps, list) else []:
            parsed = _parse_pep508(entry) if isinstance(entry, str) else None
            if not parsed:
                continue
            name, constraint = parsed
            specs.append(
                DependencySpec(
                    ecosystem="pypi",
                    name=name,
                    version_constraint=constraint,
                    resolution_method="range" if constraint else "unresolved",
                    manifest_path=manifest_path,
                    dev=True,
                )
            )

    poetry = (((data.get("tool") or {}).get("poetry")) or {})
    for section, is_dev in (("dependencies", False), ("dev-dependencies", True)):
        for name, value in (poetry.get(section) or {}).items():
            if name.lower() == "python":
                continue  # the Python version constraint itself, not a package
            if isinstance(value, str):
                constraint = value
            elif isinstance(value, dict) and isinstance(value.get("version"), str):
                constraint = value["version"]
            else:
                continue  # e.g. a git/path dependency table - not registry-resolvable
            specs.append(
                DependencySpec(
                    ecosystem="pypi",
                    name=name,
                    version_constraint=constraint,
                    resolution_method="range",
                    manifest_path=manifest_path,
                    dev=is_dev,
                )
            )
    # Poetry 1.2+ groups: [tool.poetry.group.<name>.dependencies]
    for group in ((poetry.get("group") or {})).values():
        for name, value in (group.get("dependencies") or {}).items():
            if isinstance(value, str):
                constraint = value
            elif isinstance(value, dict) and isinstance(value.get("version"), str):
                constraint = value["version"]
            else:
                continue
            specs.append(
                DependencySpec(
                    ecosystem="pypi",
                    name=name,
                    version_constraint=constraint,
                    resolution_method="range",
                    manifest_path=manifest_path,
                    dev=True,
                )
            )

    return specs


# ---------------------------------------------------------------------------
# Maven: pom.xml
# ---------------------------------------------------------------------------


def parse_pom_xml(content: str, manifest_path: str) -> list[DependencySpec]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []

    properties: dict[str, str] = {}
    props_el = _pom_find(root, "properties")
    if props_el is not None:
        for child in props_el:
            tag = child.tag.split("}")[-1]
            if child.text:
                properties[tag] = child.text.strip()

    project_version = _pom_text(root, "version")
    if project_version:
        properties.setdefault("project.version", project_version)

    def resolve_property_refs(value: str) -> Optional[str]:
        match = re.fullmatch(r"\$\{([^}]+)\}", value.strip())
        if not match:
            return value
        return properties.get(match.group(1))

    specs: list[DependencySpec] = []
    for dep in _pom_findall(root, "dependencies/dependency"):
        group_id = _pom_text(dep, "groupId")
        artifact_id = _pom_text(dep, "artifactId")
        if not group_id or not artifact_id:
            continue
        scope = _pom_text(dep, "scope") or "compile"
        if scope == "test":
            continue

        raw_version = _pom_text(dep, "version")
        version = resolve_property_refs(raw_version) if raw_version else None

        specs.append(
            DependencySpec(
                ecosystem="maven",
                name=f"{group_id}:{artifact_id}",
                version_constraint=version,
                resolution_method="exact" if version else "unresolved",
                manifest_path=manifest_path,
                dev=(scope in ("provided", "test")),
            )
        )
    return specs
