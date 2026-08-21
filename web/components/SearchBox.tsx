"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ECOSYSTEMS, DEFAULT_ECOSYSTEM, type Ecosystem } from "@/lib/scan";

const PLACEHOLDERS: Record<Ecosystem, string> = {
  npm: "e.g. axios, left-pad, @babel/core",
  pypi: "e.g. requests, numpy, flask",
  maven: "e.g. com.google.guava:guava",
};

export default function SearchBox({
  placeholder,
  autoFocus = false,
}: {
  placeholder?: string;
  autoFocus?: boolean;
}) {
  const router = useRouter();
  const [value, setValue] = useState("");
  const [ecosystem, setEcosystem] = useState<Ecosystem>(DEFAULT_ECOSYSTEM);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) return;
    router.push(`/p/${ecosystem}/${encodeURIComponent(trimmed)}`);
  }

  return (
    <form onSubmit={handleSubmit} className="flex w-full max-w-xl flex-col gap-2 sm:flex-row">
      <select
        value={ecosystem}
        onChange={(e) => setEcosystem(e.target.value as Ecosystem)}
        aria-label="Ecosystem"
        className="min-h-[44px] shrink-0 rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-foreground focus:border-accent focus:outline-none"
      >
        {ECOSYSTEMS.map((eco) => (
          <option key={eco} value={eco}>
            {eco}
          </option>
        ))}
      </select>
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder ?? PLACEHOLDERS[ecosystem]}
        autoFocus={autoFocus}
        spellCheck={false}
        autoCapitalize="off"
        autoCorrect="off"
        className="min-h-[44px] flex-1 rounded-lg border border-border bg-surface px-4 py-2.5 text-sm text-foreground placeholder:text-muted focus:border-accent focus:outline-none"
      />
      <button
        type="submit"
        disabled={!value.trim()}
        className="min-h-[44px] shrink-0 rounded-lg bg-accent px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-50"
      >
        Scan package
      </button>
    </form>
  );
}
