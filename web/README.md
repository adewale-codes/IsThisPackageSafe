# packagesafe.dev (web)

Next.js (App Router) frontend for PackageSafe. Contains no scoring logic of
its own — every result page does a live, server-side call to the Phase 1
API's `GET /scan/{package}` endpoint.

## Development

```
npm install
cp .env.example .env.local   # point at your local Phase 1 backend
npm run dev
```

Visit `http://localhost:3000`.

## Configuration

- `PACKAGESAFE_API_URL` — base URL of the PackageSafe API (server-side only,
  same pattern as the CLI's `PACKAGESAFE_API_URL`). Defaults to
  `http://localhost:8000`.
- `NEXT_PUBLIC_SITE_URL` — canonical site URL, used to resolve absolute OG
  image URLs. Defaults to `http://localhost:3000`.

## Routes

- `/` — landing page with a search box and a couple of one-click examples.
- `/p/[package]` — server-rendered result page. Fetches the scan on the
  server, so the verdict/score/findings are present in the initial HTML for
  SEO and for the OG image to have real data. Every load is a live scan —
  there's no caching layer yet (that's backend work, not built in Phase 1/2).
  Scoped packages like `@babel/core` work via the search box (percent-encoded
  into a single path segment) even though the route isn't a catch-all — a
  catch-all can't be used here because Next.js doesn't allow a metadata image
  route (`opengraph-image`) nested one level inside a catch-all segment.
- `/p/[package]/opengraph-image` — dynamically generated OG image (via
  `next/og`) showing the package name, score, and verdict, so link previews
  in Slack/X/LinkedIn aren't a generic fallback card.

### Known limitation: not-found status code

The nonexistent-package state renders a clear "not found" UI, but since the
route is fully dynamic (`fetch(..., { cache: "no-store" })`, no static
generation) Next.js doesn't flip the outer HTTP status to 404 when the page
renders that state — it stays 200. This is a Next.js App Router constraint
on dynamically-rendered routes, not something specific to this app; fixing it
properly would mean giving up per-request live scanning or moving 404
detection into middleware, both bigger changes than Phase 3's scope.

## Design system

Palette and typography are lifted from the Jobreel/Triax sibling projects'
Tailwind conventions: Jobreel's token-based `tailwind.config.ts` structure
(indigo accent, slate-tinted dark neutrals) as the base, plus Triax's
low-opacity badge-tint pattern (`color` / `bg` at 10% opacity / `border` at
25% opacity) for verdict and severity indicators, and JetBrains Mono for
numeric displays (risk score, package@version).
