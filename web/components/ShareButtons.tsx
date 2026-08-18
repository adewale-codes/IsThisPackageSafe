"use client";

import { useState } from "react";

export default function ShareButtons({
  packageName,
  verdict,
  riskScore,
}: {
  packageName: string;
  verdict: string;
  riskScore: number;
}) {
  const [copied, setCopied] = useState(false);

  const shareText = `${packageName} scored ${riskScore}/100 (${verdict}) on PackageSafe`;

  async function handleCopy() {
    const url = window.location.href;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard API unavailable; silently ignore
    }
  }

  function tweetUrl() {
    const url = typeof window !== "undefined" ? window.location.href : "";
    const params = new URLSearchParams({ text: shareText, url });
    return `https://twitter.com/intent/tweet?${params.toString()}`;
  }

  function linkedInUrl() {
    const url = typeof window !== "undefined" ? window.location.href : "";
    const params = new URLSearchParams({ url });
    return `https://www.linkedin.com/sharing/share-offsite/?${params.toString()}`;
  }

  const buttonClasses =
    "min-h-[44px] inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-surface px-4 py-2.5 text-sm font-medium text-foreground transition-colors hover:border-accent hover:text-accent";

  return (
    <div className="flex flex-wrap gap-3">
      <a
        href={tweetUrl()}
        target="_blank"
        rel="noopener noreferrer"
        className={buttonClasses}
        aria-label="Share on X"
      >
        Share on X
      </a>
      <a
        href={linkedInUrl()}
        target="_blank"
        rel="noopener noreferrer"
        className={buttonClasses}
        aria-label="Share on LinkedIn"
      >
        Share on LinkedIn
      </a>
      <button type="button" onClick={handleCopy} className={buttonClasses} aria-label="Copy link">
        {copied ? "Copied!" : "Copy link"}
      </button>
    </div>
  );
}
