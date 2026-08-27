import Link from "next/link";
import SearchBox from "@/components/SearchBox";
import EcosystemExampleCycle from "@/components/EcosystemExampleCycle";

const EXAMPLES = ["axios", "left-pad", "reactt"];

export default function HomePage() {
  return (
    <main>
      <section className="mx-auto flex max-w-5xl flex-col items-center px-6 pb-16 pt-20 text-center sm:pt-28">
        <h1 className="text-3xl font-bold leading-tight tracking-tight sm:text-5xl">
          Know what you&apos;re really <span className="font-light text-accent">installing</span>.
        </h1>
        <p className="mt-5 max-w-2xl text-base text-muted sm:text-lg">
          PackageSafe scores any npm, PyPI, or Maven package for supply-chain risk in
          seconds - typosquats, maintainer takeovers, sketchy install scripts, and more -
          before it ends up in your lockfile.
        </p>

        <div className="mt-8 flex w-full justify-center">
          <EcosystemExampleCycle />
        </div>

        <div className="mt-6 flex w-full justify-center">
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
          <p className="mt-3 max-w-2xl text-muted">
            Not an AI score - an auditable pipeline of three independent signals, each shown
            separately on every result: deterministic supply-chain heuristics, real CVE/GHSA data
            from OSV.dev, and an LLM source-code review that only runs when the heuristics already
            flagged something.
          </p>
          <Link
            href="/how-it-works"
            className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-accent hover:underline"
          >
            Read the full breakdown
            <span aria-hidden="true">→</span>
          </Link>
        </div>
      </section>
    </main>
  );
}
