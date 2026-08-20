import { ImageResponse } from "next/og";
import { scanPackage, PackageNotFoundError } from "@/lib/scan";

export const runtime = "edge";
export const alt = "PackageSafe risk score";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const VERDICT_COLORS: Record<string, string> = {
  safe: "#16a34a",
  suspicious: "#d97706",
  investigate: "#dc2626",
};

export default async function OpengraphImage({
  params,
}: {
  params: { package: string };
}) {
  const packageName = params.package;

  try {
    const result = await scanPackage(packageName);
    const color = VERDICT_COLORS[result.verdict] ?? VERDICT_COLORS.investigate;
    const verdictLabel = result.verdict.toUpperCase();

    return new ImageResponse(
      (
        <div
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            backgroundColor: "#ffffff",
            padding: "64px",
            fontFamily: "sans-serif",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <div
              style={{
                display: "flex",
                width: "14px",
                height: "14px",
                borderRadius: "9999px",
                backgroundColor: "#4f46e5",
              }}
            />
            <div style={{ display: "flex", fontSize: 28, color: "#1e293b", fontWeight: 700 }}>
              PackageSafe
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column" }}>
            <div style={{ display: "flex", fontSize: 44, color: "#1e293b", fontWeight: 700 }}>
              {result.package}
              <span style={{ color: "#64748b", marginLeft: 12 }}>@{result.resolved_version}</span>
            </div>

            <div style={{ display: "flex", alignItems: "baseline", marginTop: 36, gap: "20px" }}>
              <div style={{ display: "flex", fontSize: 160, fontWeight: 700, color }}>
                {result.risk_score}
              </div>
              <div style={{ display: "flex", fontSize: 36, color: "#64748b" }}>/ 100</div>
            </div>

            <div
              style={{
                display: "flex",
                marginTop: 24,
                alignSelf: "flex-start",
                fontSize: 28,
                fontWeight: 700,
                color,
                backgroundColor: `${color}1a`,
                border: `2px solid ${color}66`,
                borderRadius: 9999,
                padding: "10px 28px",
              }}
            >
              {verdictLabel}
            </div>
          </div>

          <div style={{ display: "flex", fontSize: 22, color: "#64748b" }}>
            packagesafe.dev/p/{result.package}
          </div>
        </div>
      ),
      { ...size }
    );
  } catch (err) {
    const notFound = err instanceof PackageNotFoundError;
    return new ImageResponse(
      (
        <div
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            alignItems: "center",
            gap: "16px",
            backgroundColor: "#ffffff",
            fontFamily: "sans-serif",
          }}
        >
          <div style={{ display: "flex", fontSize: 40, color: "#1e293b", fontWeight: 700 }}>
            PackageSafe
          </div>
          <div style={{ display: "flex", fontSize: 28, color: "#64748b" }}>
            {notFound ? `'${packageName}' was not found on npm` : "Unable to scan this package"}
          </div>
        </div>
      ),
      { ...size }
    );
  }
}
