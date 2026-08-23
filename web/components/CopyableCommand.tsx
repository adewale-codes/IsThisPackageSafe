"use client";

import { useState } from "react";

export default function CopyableCommand({ command }: { command: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard API unavailable; silently ignore
    }
  }

  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface px-4 py-3 font-mono text-sm">
      <code className="overflow-x-auto text-foreground">{command}</code>
      <button
        type="button"
        onClick={handleCopy}
        className="shrink-0 rounded-md border border-border px-2 py-1 text-xs text-muted transition-colors hover:border-accent hover:text-accent"
        aria-label="Copy command"
      >
        {copied ? "Copied!" : "Copy"}
      </button>
    </div>
  );
}
