import { buildRegistryUrl, registryLabel } from "@/lib/registryLink";
import type { Ecosystem } from "@/lib/scan";

/**
 * Phase 11: small, unmissable, opens in a new tab - meant to build trust
 * ("verify this yourself against the real registry"), not to replace the
 * page itself.
 */
export default function RegistryLink({
  ecosystem,
  packageName,
  version,
}: {
  ecosystem: Ecosystem;
  packageName: string;
  version: string;
}) {
  const url = buildRegistryUrl(ecosystem, packageName, version);
  const label = registryLabel(ecosystem);

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:underline"
    >
      View on {label}
      <span aria-hidden="true">↗</span>
    </a>
  );
}
