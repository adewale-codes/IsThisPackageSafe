from app.services.ecosystems.base import EcosystemClient, PackageNotFoundError
from app.services.ecosystems.maven import MavenClient
from app.services.ecosystems.npm import NpmClient
from app.services.ecosystems.pypi import PyPIClient

CLIENTS: dict[str, EcosystemClient] = {
    "npm": NpmClient(),
    "pypi": PyPIClient(),
    "maven": MavenClient(),
}

SUPPORTED_ECOSYSTEMS = tuple(sorted(CLIENTS))


def get_client(ecosystem: str) -> EcosystemClient:
    try:
        return CLIENTS[ecosystem]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported ecosystem {ecosystem!r}. Supported: {', '.join(SUPPORTED_ECOSYSTEMS)}"
        ) from exc


__all__ = [
    "EcosystemClient",
    "PackageNotFoundError",
    "CLIENTS",
    "SUPPORTED_ECOSYSTEMS",
    "get_client",
]
