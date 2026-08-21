export default function Loading() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <div className="animate-pulse rounded-2xl border border-border bg-surface p-6 sm:p-8">
        <div className="flex items-start justify-between gap-4">
          <div className="flex flex-col gap-2">
            <div className="h-7 w-48 rounded bg-border" />
            <div className="h-4 w-64 rounded bg-border" />
          </div>
          <div className="h-8 w-24 rounded-full bg-border" />
        </div>
        <div className="mt-6 h-10 w-32 rounded bg-border" />
        <div className="mt-6 grid grid-cols-2 gap-4 border-t border-border pt-5 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex flex-col gap-2">
              <div className="h-3 w-16 rounded bg-border" />
              <div className="h-4 w-12 rounded bg-border" />
            </div>
          ))}
        </div>
      </div>
      <p className="mt-6 text-center text-sm text-muted">
        Scanning package - this fetches live data from the npm registry and GitHub, so it can take
        a few seconds…
      </p>
    </main>
  );
}
