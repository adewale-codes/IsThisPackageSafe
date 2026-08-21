import { redirect } from "next/navigation";

// Legacy single-segment alias for ecosystem=npm, from before
// /p/[ecosystem]/[package] existed. Kept so pre-Phase-7 links (bookmarks,
// READMEs, shared results) keep working. Despite the folder name (shared
// with the real /p/[ecosystem]/[package] route one level down - Next.js
// requires sibling dynamic segments at the same depth to share a slug
// name), this route's single segment holds a *package* name, not an
// ecosystem; ecosystem=npm is implied.
export default function LegacyPackageResultPage({
  params,
}: {
  params: { ecosystem: string };
}) {
  // Next.js 14.2.35 doesn't reliably percent-decode this param for nested
  // Page routes (see decodeParam's comment in [package]/page.tsx); decode
  // explicitly, then re-encode so a literal "/" (e.g. scoped npm package
  // "@babel/core") is preserved as one path segment, not split in two.
  let packageName = params.ecosystem;
  try {
    packageName = decodeURIComponent(packageName);
  } catch {
    // leave as-is if not validly encoded
  }
  redirect(`/p/npm/${encodeURIComponent(packageName)}`);
}
