import Link from "next/link";
import SearchBox from "@/components/SearchBox";

const EXAMPLES = ["axios", "left-pad", "reactt"];

export default function HomePage() {
  return (
    <main>
      <section className="mx-auto flex max-w-5xl flex-col items-center px-6 pb-16 pt-20 text-center sm:pt-28">
        <h1 className="text-3xl font-bold leading-tight tracking-tight sm:text-5xl">
          Know what you&apos;re really{" "}
          <span className="font-light text-accent">npm install</span>ing.
        </h1>
        <p className="mt-5 max-w-2xl text-base text-muted sm:text-lg">
          PackageSafe scores any npm package for supply-chain risk in seconds -
          typosquats, maintainer takeovers, sketchy install scripts, and more -
          before it ends up in your lockfile.
        </p>

        <div className="mt-10 flex w-full justify-center">
          <SearchBox autoFocus />
        </div>

        <div className="mt-6 flex flex-wrap items-center justify-center gap-2 text-sm text-muted">
          <span>Try it:</span>
          {EXAMPLES.map((name, i) => (
            <span key={name} className="flex items-center gap-2">
              <Link href={`/p/npm/${name}`} className="text-accent hover:underline">
                {name}
              </Link>
              {i < EXAMPLES.length - 1 && <span className="text-border">·</span>}
            </span>
          ))}
        </div>
      </section>

      <section className="border-t border-border bg-surface">
        <div className="mx-auto max-w-5xl px-6 py-16 sm:py-24">
          <h2 className="text-2xl font-bold sm:text-3xl">How it works</h2>
          <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2">
            <div className="rounded-xl border border-border bg-background p-5">
              <h3 className="text-base font-semibold text-accent">
                1. Deterministic heuristics
              </h3>
              <p className="mt-2 text-sm text-muted">
                Every scan runs a fixed set of checks against the npm registry and
                GitHub: package age, maintainer change history, install scripts,
                typosquatting, dependency count, and repo/npm activity mismatches.
                Each contributes points to a 0–100 risk score - no LLM involved,
                so results are fast and reproducible.
              </p>
            </div>
            <div className="rounded-xl border border-border bg-background p-5">
              <h3 className="text-base font-semibold text-accent">
                2. LLM deep scan (coming soon)
              </h3>
              <p className="mt-2 text-sm text-muted">
                Packages that already score as suspicious, or trip a
                danger-severity finding, get flagged for a deeper LLM-driven
                source inspection - looking for obfuscated payloads or
                exfiltration code that static rules alone would miss. This
                layer is still in development.
              </p>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
