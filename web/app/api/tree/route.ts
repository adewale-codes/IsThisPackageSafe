import { NextRequest, NextResponse } from "next/server";
import { buildScanUrl, ECOSYSTEMS, type Ecosystem } from "@/lib/scan";

/**
 * Phase 8: server-side proxy for the dependency-tree fetch. Route Handlers
 * (unlike Server Components) run on every request rather than being cached
 * for a page load, which is what we want here - a tree scan is a slow,
 * on-demand action a user explicitly triggers (see DependencyTreeSection),
 * not something to compute on every page render. Proxying through here
 * (rather than having the browser call the backend directly) keeps
 * PACKAGESAFE_API_URL server-only, consistent with the rest of the site.
 */
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const ecosystem = searchParams.get("ecosystem");
  const packageName = searchParams.get("package");
  const version = searchParams.get("version") || undefined;
  const maxDepth = searchParams.get("max_depth");
  const nodeCap = searchParams.get("node_cap");

  if (!ecosystem || !(ECOSYSTEMS as string[]).includes(ecosystem) || !packageName) {
    return NextResponse.json(
      { detail: "Missing or invalid 'ecosystem'/'package' query params." },
      { status: 400 }
    );
  }

  const url = buildScanUrl(packageName, ecosystem as Ecosystem, {
    version,
    includeTree: true,
    maxDepth: maxDepth ? Number(maxDepth) : undefined,
    nodeCap: nodeCap ? Number(nodeCap) : undefined,
  });

  try {
    const resp = await fetch(url, { cache: "no-store" });
    const body = await resp.json();
    return NextResponse.json(body, { status: resp.status });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      { detail: `Could not reach the PackageSafe API (${message}). Is the backend running?` },
      { status: 502 }
    );
  }
}
