import type { Metadata } from "next";
import Link from "next/link";
import CopyableCommand from "@/components/CopyableCommand";

export const metadata: Metadata = {
  title: "safecheck CLI - PackageSafe",
  description:
    "Free, open-source command-line tool for PackageSafe. Scan npm, PyPI, and Maven packages - or a whole repo's dependencies - for supply-chain risk without leaving your terminal.",
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-10">
      <h2 className="text-lg font-semibold">{title}</h2>
      <div className="mt-3 flex flex-col gap-3">{children}</div>
    </section>
  );
}

function Code({ children }: { children: React.ReactNode }) {
  return (
    <pre className="overflow-x-auto rounded-lg border border-border bg-surface px-4 py-3 font-mono text-sm text-foreground">
      <code>{children}</code>
    </pre>
  );
}

export default function CliPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <p className="text-xs uppercase tracking-widest text-muted">Free &amp; open source</p>
      <h1 className="mt-2 font-mono text-3xl font-bold sm:text-4xl">safecheck</h1>
      <p className="mt-3 max-w-xl text-muted">
        The same supply-chain risk scanning that powers this website, in your terminal. Scan a
        single package, its full dependency tree, or your whole repo&apos;s manifests - no account,
        no browser, works great in CI.
      </p>

      <div className="mt-6 flex flex-wrap gap-3">
        <a
          href="https://www.npmjs.com/package/safecheck"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex min-h-[44px] items-center justify-center rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-accent/90"
        >
          View on npm
        </a>
        <a
          href="https://github.com/adewale-codes/IsThisPackageSafe"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex min-h-[44px] items-center justify-center rounded-lg border border-border bg-surface px-5 py-2.5 text-sm font-medium text-foreground transition-colors hover:border-accent hover:text-accent"
        >
          View on GitHub
        </a>
      </div>

      <Section title="Install">
        <p className="text-sm text-muted">Try it once, no install:</p>
        <CopyableCommand command="npx safecheck axios" />

        <p className="mt-2 text-sm text-muted">Install globally, use it anywhere:</p>
        <CopyableCommand command="npm install -g safecheck" />

        <p className="mt-2 text-sm text-muted">
          Or add it to a project as a dev dependency, so a security check works for anyone who
          clones the repo:
        </p>
        <CopyableCommand command="npm install --save-dev safecheck" />
      </Section>

      <Section title="Scan a package">
        <p className="text-sm text-muted">Latest version, npm assumed:</p>
        <Code>safecheck axios</Code>

        <p className="mt-2 text-sm text-muted">A specific version:</p>
        <Code>safecheck axios@1.2.0</Code>

        <p className="mt-2 text-sm text-muted">A non-npm package - prefix with the ecosystem:</p>
        <Code>{`safecheck pypi:requests
safecheck maven:com.google.guava:guava`}</Code>

        <p className="mt-2 text-sm text-muted">Include its full dependency tree:</p>
        <Code>safecheck axios --tree</Code>
      </Section>

      <Section title="Scan a whole repo">
        <p className="text-sm text-muted">
          Run with no arguments inside a directory with a manifest (
          <code className="font-mono">package.json</code>, <code className="font-mono">requirements.txt</code>,{" "}
          <code className="font-mono">pyproject.toml</code>, or{" "}
          <code className="font-mono">pom.xml</code>) and it auto-detects and scans everything -
          direct and transitive dependencies, across every manifest found:
        </p>
        <Code>{`cd my-project
safecheck`}</Code>

        <p className="mt-2 text-sm text-muted">Or scan a specific path from anywhere:</p>
        <Code>safecheck scan ./some-other-repo</Code>

        <p className="mt-2 text-sm text-muted">
          Add it as a project script so it&apos;s one command away for anyone who clones the repo:
        </p>
        <Code>{`"scripts": { "security-check": "safecheck" }`}</Code>
      </Section>

      <Section title="Use it as a CI gate">
        <p className="text-sm text-muted">
          Exit code <code className="font-mono">0</code> means safe, <code className="font-mono">1</code> means
          the worst verdict found was suspicious/investigate (or something couldn&apos;t be scanned):
        </p>
        <Code>{`safecheck || exit 1`}</Code>
      </Section>

      <Section title="Full reference">
        <p className="text-sm text-muted">
          <code className="font-mono">safecheck --help</code> lists every option -{" "}
          <code className="font-mono">--json</code> for machine-readable output,{" "}
          <code className="font-mono">--max-depth</code>/<code className="font-mono">--node-cap</code> to tune
          dependency-tree exploration, <code className="font-mono">--api-url</code> to point at a
          self-hosted backend, and more. The full README is on{" "}
          <a
            href="https://github.com/adewale-codes/IsThisPackageSafe/tree/main/cli"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent hover:underline"
          >
            GitHub
          </a>
          .
        </p>
      </Section>

      <section className="mt-12 rounded-2xl border border-border bg-surface p-6 text-sm text-muted">
        Want dependency-tree visualization, shareable result pages, or just don&apos;t want to open a
        terminal? Use the full experience on{" "}
        <Link href="/" className="text-accent hover:underline">
          the PackageSafe website
        </Link>
        .
      </section>
    </main>
  );
}
