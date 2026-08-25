import Link from "next/link";

export default function Navbar() {
  return (
    <nav className="border-b border-border bg-surface">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
        <Link href="/" className="text-sm font-semibold tracking-tight text-foreground">
          Package<span className="text-accent">Safe</span>
        </Link>
        <div className="flex items-center gap-4">
          <Link
            href="/how-it-works"
            className="text-xs uppercase tracking-widest text-muted hover:text-accent"
          >
            How it works
          </Link>
          <Link href="/cli" className="text-xs uppercase tracking-widest text-muted hover:text-accent">
            CLI
          </Link>
          <Link
            href="/transparency"
            className="text-xs uppercase tracking-widest text-muted hover:text-accent"
          >
            Transparency
          </Link>
          <span className="hidden text-xs uppercase tracking-widest text-muted sm:inline">
            supply-chain risk scanner
          </span>
        </div>
      </div>
    </nav>
  );
}
