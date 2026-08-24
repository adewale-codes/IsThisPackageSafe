import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "How it works - PackageSafe",
  description:
    "PackageSafe isn't an AI score - it's an auditable pipeline of three independent, individually inspectable signals: deterministic heuristics, real CVE data, and an LLM source-code review that only runs when warranted.",
};

function Layer({
  number,
  title,
  tagline,
  children,
}: {
  number: string;
  title: string;
  tagline: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-6 sm:p-8">
      <div className="flex items-baseline gap-3">
        <span className="font-mono text-sm text-muted">{number}</span>
        <h2 className="text-xl font-bold">{title}</h2>
      </div>
      <p className="mt-1 text-sm font-medium text-accent">{tagline}</p>
      <div className="mt-4 flex flex-col gap-3 text-sm text-muted">{children}</div>
    </div>
  );
}

export default function HowItWorksPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="text-3xl font-bold sm:text-4xl">How it works</h1>
      <p className="mt-4 max-w-xl text-muted">
        PackageSafe is not an AI score. A risk score is the sum of three independent, individually
        inspectable signals - a deterministic rules engine, real published vulnerability data, and
        an LLM source review that only runs when the first layer already flagged something. Every
        result page shows you exactly which of these contributed points and why, so you&apos;re never
        just trusting a number.
      </p>

      <div className="mt-10 flex flex-col gap-6">
        <Layer
          number="01"
          title="Supply-chain heuristics"
          tagline="Deterministic. Free. Runs on every single scan."
        >
          <p>
            A fixed set of rules against registry metadata and, where a repository is linked,
            GitHub activity. No model involved - the same input always produces the same output,
            and every rule is a plain function you can read the source of:
          </p>
          <ul className="ml-4 list-disc space-y-1">
            <li>
              <strong className="text-foreground">Package age</strong> - published under 7 or 30
              days ago is itself a risk signal for a brand-new dependency.
            </li>
            <li>
              <strong className="text-foreground">Maintainer takeover</strong> (npm only - the only
              registry that exposes per-version maintainer history) - every maintainer replaced at
              once between two versions, a classic account-compromise pattern.
            </li>
            <li>
              <strong className="text-foreground">Install scripts</strong> (npm only) - lifecycle
              scripts (<code className="font-mono text-xs">preinstall</code>/
              <code className="font-mono text-xs">install</code>/
              <code className="font-mono text-xs">postinstall</code>) that run automatically the
              moment the package is installed.
            </li>
            <li>
              <strong className="text-foreground">Typosquatting</strong> - name within a short edit
              distance of a popular package in the same ecosystem, but not an exact match.
            </li>
            <li>
              <strong className="text-foreground">Dependency count</strong> - an unusually large
              direct dependency count widens the attack surface.
            </li>
            <li>
              <strong className="text-foreground">Repo/release activity mismatch</strong> - a recent
              release with no matching recent commit activity in the linked repository.
            </li>
            <li>
              <strong className="text-foreground">Popularity anomaly</strong> - high download counts
              paired with a near-empty GitHub footprint (few stars, effectively one contributor).
            </li>
          </ul>
          <p>
            A few of these are npm-specific because the signal they need genuinely doesn&apos;t exist
            in PyPI&apos;s or Maven Central&apos;s APIs - rather than fake a result, those checks are
            simply not run for those ecosystems, and the result page says so.
          </p>
        </Layer>

        <Layer
          number="02"
          title="Known vulnerabilities"
          tagline="Real CVE/GHSA data from OSV.dev - a separate signal from #1."
        >
          <p>
            Every scan is also checked against{" "}
            <a
              href="https://osv.dev"
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent hover:underline"
            >
              OSV.dev
            </a>
            , the aggregated open-source vulnerability database, for the exact package and version
            being scanned. This answers a genuinely different question than layer 1:{" "}
            <em>&quot;does this package behave suspiciously&quot;</em> versus{" "}
            <em>&quot;does this exact version have a publicly disclosed vulnerability.&quot;</em> A
            completely legitimate, well-maintained package can still carry a real CVE - that&apos;s
            not a contradiction, and the two are always shown as separate sections so one can&apos;t
            be mistaken for the other. Severity (critical/high/medium/low) is read directly from the
            advisory or computed from its CVSS vector when only a raw score is published.
          </p>
          <p>
            For a full repo scan, every dependency&apos;s vulnerability check is batched into a
            handful of requests rather than one network round-trip per package, so checking hundreds
            of direct and transitive dependencies stays fast.
          </p>
        </Layer>

        <Layer
          number="03"
          title="LLM deep-scan"
          tagline="Claude reading actual source code - only when layer 1 already flagged something."
        >
          <p>
            The first two layers are metadata-only - fast, but they can&apos;t see what a package
            actually <em>does</em>. When the heuristics score crosses a threshold, or any single
            heuristic flags at danger severity, PackageSafe downloads the real package tarball,
            unpacks it, and selects a small high-signal subset of source files: anything referenced
            by an install script, the package&apos;s entry point, and any file that trips a
            suspicion filter (minified-looking code, unusually long lines, <code className="font-mono text-xs">eval()</code>,
            dynamic <code className="font-mono text-xs">Function()</code> construction, spawning
            child processes, decoding base64 payloads, reading <code className="font-mono text-xs">process.env</code>).
          </p>
          <p>
            Those excerpts, plus the package&apos;s name and stated description, go to Claude with one
            job: does this code plausibly do what a package like this claims to do, or does it show
            obfuscation, unexplained network calls, or data-exfiltration patterns? The result is a
            bounded, structured classification, not free-form text - and it&apos;s deliberately gated
            behind layer 1 rather than run on every scan, since it&apos;s the slow, costly layer and
            most packages never need it.
          </p>
          <p>
            If the download or the model call fails for any reason, the result says so explicitly
            (&quot;deep scan did not complete&quot;) rather than silently reporting a clean result -
            a failed check must never look identical to a real one.
          </p>
        </Layer>
      </div>

      <section className="mt-10 rounded-2xl border border-border bg-surface p-6 text-sm text-muted">
        <h2 className="text-base font-semibold text-foreground">Beyond a single package</h2>
        <p className="mt-2">
          The same three-layer pipeline runs at every scope PackageSafe supports: a single package
          at latest or a pinned version, its full transitive dependency tree (so &quot;this package
          is fine, but depends on X which has a CVE&quot; is visible, not buried), or an entire
          repo&apos;s manifests scanned at once. It&apos;s the same auditable signals throughout - just
          applied to more packages at a time.
        </p>
      </section>

      <section className="mt-8 flex justify-center">
        <Link
          href="/"
          className="inline-flex min-h-[44px] items-center justify-center rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-accent/90"
        >
          Try a scan
        </Link>
      </section>
    </main>
  );
}
