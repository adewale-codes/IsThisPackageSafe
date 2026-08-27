"use client";

import { useEffect, useState } from "react";

const EXAMPLES = [
  { ecosystem: "npm", command: "safecheck axios" },
  { ecosystem: "PyPI", command: "safecheck pypi:requests" },
  { ecosystem: "Maven", command: "safecheck maven:com.google.guava:guava" },
];

// Fully visible for ~3.7s, then a quick 300ms fade before the next example -
// comfortably above the "3-4 seconds minimum to actually read it" floor.
const HOLD_MS = 4000;
const FADE_MS = 300;

/**
 * A visitor's first impression of this site was, until now, exclusively
 * npm-framed (headline, examples, all of it) - this cycles the same CLI
 * command across all three supported ecosystems so that's obvious at a
 * glance, without needing a real animation library for what's just a
 * timed opacity transition.
 */
export default function EcosystemExampleCycle() {
  const [index, setIndex] = useState(0);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const fadeOut = setTimeout(() => setVisible(false), HOLD_MS - FADE_MS);
    const advance = setTimeout(() => {
      setIndex((i) => (i + 1) % EXAMPLES.length);
      setVisible(true);
    }, HOLD_MS);
    return () => {
      clearTimeout(fadeOut);
      clearTimeout(advance);
    };
  }, [index]);

  const current = EXAMPLES[index];

  return (
    <div className="flex w-full max-w-xl items-center gap-3 rounded-lg border border-border bg-surface px-5 py-3 font-mono text-sm">
      <span className="text-muted" aria-hidden="true">
        $
      </span>
      <span
        className="flex-1 text-left transition-opacity ease-in-out"
        style={{ opacity: visible ? 1 : 0, transitionDuration: `${FADE_MS}ms` }}
      >
        {current.command}
      </span>
      <span className="shrink-0 text-xs uppercase tracking-widest text-muted">{current.ecosystem}</span>
    </div>
  );
}
