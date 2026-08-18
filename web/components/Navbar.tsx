import Link from "next/link";

export default function Navbar() {
  return (
    <nav className="border-b border-border bg-surface">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
        <Link href="/" className="text-sm font-semibold tracking-tight text-foreground">
          Package<span className="text-accent">Safe</span>
        </Link>
        <span className="text-xs uppercase tracking-widest text-muted">npm risk scanner</span>
      </div>
    </nav>
  );
}
