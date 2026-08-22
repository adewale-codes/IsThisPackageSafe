import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import SearchBox from "@/components/SearchBox";
import ScanResultView from "@/components/ScanResultView";
import {
  scanPackage,
  fetchVersions,
  PackageNotFoundError,
  NetworkError,
  ApiError,
  ECOSYSTEMS,
  type Ecosystem,
  type ScanResult,
  type VersionEntry,
} from "@/lib/scan";

export const dynamic = "force-dynamic";

type PageParams = { ecosystem: string; package: string; version: string };

function isEcosystem(value: string): value is Ecosystem {
  return (ECOSYSTEMS as string[]).includes(value);
}

// See the sibling [package]/page.tsx for why this decode is necessary
// (this Next.js version doesn't reliably percent-decode nested Page params).
function decodeParam(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

export async function generateMetadata({
  params,
}: {
  params: PageParams;
}): Promise<Metadata> {
  const ecosystem = decodeParam(params.ecosystem);
  const packageName = decodeParam(params.package);
  const version = decodeParam(params.version);
  if (!isEcosystem(ecosystem)) {
    return { title: "Unknown ecosystem" };
  }

  try {
    const result = await scanPackage(packageName, ecosystem, { version });
    const verdictLabel = result.verdict[0].toUpperCase() + result.verdict.slice(1);
    return {
      title: `${result.package}@${result.resolved_version} - ${verdictLabel} (${result.risk_score}/100)`,
      description: `${result.package}@${result.resolved_version} scored ${result.risk_score}/100 on PackageSafe (${result.verdict}). See the full risk breakdown.`,
    };
  } catch {
    return {
      title: `${packageName}@${version} - not found`,
      description: `PackageSafe could not find '${packageName}@${version}' in the ${ecosystem} registry.`,
    };
  }
}

export default async function PinnedPackageResultPage({ params }: { params: PageParams }) {
  const ecosystem = decodeParam(params.ecosystem);
  const packageName = decodeParam(params.package);
  const version = decodeParam(params.version);
  if (!isEcosystem(ecosystem)) {
    notFound();
  }

  let result: ScanResult;
  try {
    result = await scanPackage(packageName, ecosystem, { version });
  } catch (err) {
    if (err instanceof PackageNotFoundError) {
      return <NotFoundState packageName={packageName} version={version} ecosystem={ecosystem} />;
    }
    if (err instanceof NetworkError || err instanceof ApiError) {
      return <ErrorState packageName={packageName} version={version} message={err.message} />;
    }
    return (
      <ErrorState
        packageName={packageName}
        version={version}
        message="Something went wrong while scanning this package."
      />
    );
  }

  let versions: VersionEntry[] | null = null;
  try {
    versions = await fetchVersions(packageName, ecosystem);
  } catch {
    versions = null;
  }

  return <ScanResultView result={result} versions={versions} pinnedVersion={version} />;
}

function NotFoundState({
  packageName,
  version,
  ecosystem,
}: {
  packageName: string;
  version: string;
  ecosystem: Ecosystem;
}) {
  return (
    <main className="mx-auto flex max-w-xl flex-col items-center px-6 py-24 text-center">
      <span className="text-5xl">🔎</span>
      <h1 className="mt-4 text-xl font-bold">Version not found</h1>
      <p className="mt-2 text-sm text-muted">
        <span className="font-mono text-foreground">
          {packageName}@{version}
        </span>{" "}
        was not found in the {ecosystem} registry. Double-check the version, or try another
        package below.
      </p>
      <div className="mt-8 w-full">
        <SearchBox />
      </div>
      <Link href="/" className="mt-6 text-sm text-accent hover:underline">
        ← Back to PackageSafe
      </Link>
    </main>
  );
}

function ErrorState({
  packageName,
  version,
  message,
}: {
  packageName: string;
  version: string;
  message: string;
}) {
  return (
    <main className="mx-auto flex max-w-xl flex-col items-center px-6 py-24 text-center">
      <span className="text-5xl">⚠️</span>
      <h1 className="mt-4 text-xl font-bold">
        Couldn&apos;t scan {packageName}@{version}
      </h1>
      <p className="mt-2 text-sm text-muted">{message}</p>
      <Link href="/" className="mt-6 text-sm text-accent hover:underline">
        ← Back to PackageSafe
      </Link>
    </main>
  );
}
