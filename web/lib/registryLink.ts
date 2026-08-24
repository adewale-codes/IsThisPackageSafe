import type { Ecosystem } from "./scan";

/**
 * Phase 11: a direct link to the actual registry page for the exact
 * package+version being shown, so a user can independently verify what
 * PackageSafe is describing rather than just trusting the score.
 *
 * Maven deliberately links repo1.maven.org (the raw artifact repository)
 * rather than search.maven.org's nicer search UI - Phase 7 found the
 * search index measurably lags behind what's actually published (a
 * version can exist on repo1 before search.maven.org indexes it), so for
 * a "verify this yourself" link, the always-authoritative raw repo is the
 * more honest choice even though it's a plainer page.
 */
export function buildRegistryUrl(ecosystem: Ecosystem, packageName: string, version: string): string {
  switch (ecosystem) {
    case "npm":
      return `https://www.npmjs.com/package/${packageName}/v/${version}`;
    case "pypi":
      return `https://pypi.org/project/${packageName}/${version}/`;
    case "maven": {
      const [groupId, artifactId] = packageName.split(":");
      const groupPath = (groupId || "").split(".").join("/");
      return `https://repo1.maven.org/maven2/${groupPath}/${artifactId}/${version}/`;
    }
    default:
      return "#";
  }
}

export function registryLabel(ecosystem: Ecosystem): string {
  switch (ecosystem) {
    case "npm":
      return "npmjs.com";
    case "pypi":
      return "pypi.org";
    case "maven":
      return "repo1.maven.org";
    default:
      return "registry";
  }
}
