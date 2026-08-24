import { VERDICT_CONFIG } from "@/components/VerdictBadge";
import type { Ecosystem, FlaggedDependency, Verdict } from "@/lib/scan";

interface ChainNode {
  name: string;
  children: ChainNode[];
  flagged?: FlaggedDependency;
}

interface PositionedNode extends ChainNode {
  x: number;
  y: number;
  children: PositionedNode[];
}

/**
 * Merges every flagged dependency's root-to-node path into one tree, so
 * shared prefixes (the extremely common "many packages depend on the same
 * transitive dependency" case) collapse into a single branch rather than
 * being drawn once per flagged dependency that happens to route through it.
 */
function buildChainTree(rootName: string, flagged: FlaggedDependency[]): ChainNode {
  const root: ChainNode = { name: rootName, children: [] };
  for (const dep of flagged) {
    let current = root;
    // path[0] is always rootName - the root node above already represents it.
    for (let i = 1; i < dep.path.length; i++) {
      const segment = dep.path[i];
      let child = current.children.find((c) => c.name === segment);
      if (!child) {
        child = { name: segment, children: [] };
        current.children.push(child);
      }
      current = child;
    }
    current.flagged = dep;
  }
  return root;
}

const NODE_W = 168;
const NODE_H = 56;
const H_GAP = 24;
const V_GAP = 56;

/** Simple top-down tree layout: leaves get evenly spaced x positions
 * left-to-right, each parent centers over its children, y is depth-based.
 * Deliberately plain - this isn't the place to pull in a full graph-layout
 * library for what's usually a handful of flagged nodes. */
function layout(node: ChainNode, depth: number, cursor: { x: number }): PositionedNode {
  if (node.children.length === 0) {
    const x = cursor.x;
    cursor.x += NODE_W + H_GAP;
    return { ...node, x, y: depth * (NODE_H + V_GAP), children: [] };
  }
  const children = node.children.map((c) => layout(c, depth + 1, cursor));
  const x = (children[0].x + children[children.length - 1].x) / 2;
  return { ...node, x, y: depth * (NODE_H + V_GAP), children };
}

function flattenNodes(node: PositionedNode): PositionedNode[] {
  return [node, ...node.children.flatMap(flattenNodes)];
}

function flattenEdges(node: PositionedNode): [PositionedNode, PositionedNode][] {
  return [
    ...node.children.map((c): [PositionedNode, PositionedNode] => [node, c]),
    ...node.children.flatMap(flattenEdges),
  ];
}

function nodeColor(verdict?: Verdict): { fg: string; bg: string; border: string } {
  const cfg = verdict ? VERDICT_CONFIG[verdict] : undefined;
  return cfg
    ? { fg: cfg.color, bg: cfg.bg, border: cfg.border }
    : { fg: "var(--foreground, #333)", bg: "var(--surface, #f5f5f5)", border: "var(--border, #ddd)" };
}

function packageUrl(ecosystem: Ecosystem, name: string, version?: string): string {
  const encoded = name
    .split("/")
    .map((s) => encodeURIComponent(s))
    .join("/");
  return version ? `/p/${ecosystem}/${encoded}/${encodeURIComponent(version)}` : `/p/${ecosystem}/${encoded}`;
}

export default function DependencyChainViz({
  ecosystem,
  rootPackage,
  rootVerdict,
  flaggedDependencies,
}: {
  ecosystem: Ecosystem;
  rootPackage: string;
  rootVerdict: Verdict;
  flaggedDependencies: FlaggedDependency[];
}) {
  if (flaggedDependencies.length === 0) return null;

  const tree = buildChainTree(rootPackage, flaggedDependencies);
  const positioned = layout(tree, 0, { x: 0 });
  const nodes = flattenNodes(positioned);
  const edges = flattenEdges(positioned);

  const width = Math.max(...nodes.map((n) => n.x)) + NODE_W;
  const height = Math.max(...nodes.map((n) => n.y)) + NODE_H;

  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-surface p-4">
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`Dependency chain from ${rootPackage} to its flagged dependencies`}
      >
        {edges.map(([from, to], i) => {
          const x1 = from.x + NODE_W / 2;
          const y1 = from.y + NODE_H;
          const x2 = to.x + NODE_W / 2;
          const y2 = to.y;
          const midY = (y1 + y2) / 2;
          return (
            <path
              key={i}
              d={`M ${x1} ${y1} C ${x1} ${midY}, ${x2} ${midY}, ${x2} ${y2}`}
              fill="none"
              stroke="var(--border, #ccc)"
              strokeWidth={2}
            />
          );
        })}

        {nodes.map((node) => {
          const isRoot = node === positioned;
          const verdict = isRoot ? rootVerdict : node.flagged?.verdict;
          const { fg, bg, border } = nodeColor(verdict);
          const href = isRoot ? null : packageUrl(ecosystem, node.name, node.flagged?.version);
          const label = node.flagged ? `${node.name}@${node.flagged.version}` : node.name;
          const sublabel = isRoot
            ? "root"
            : node.flagged
              ? `risk ${node.flagged.risk_score}/100`
              : "not flagged";

          const content = (
            <g>
              <rect
                x={node.x}
                y={node.y}
                width={NODE_W}
                height={NODE_H}
                rx={10}
                fill={bg}
                stroke={border}
                strokeWidth={isRoot ? 2 : 1.5}
              />
              <text
                x={node.x + NODE_W / 2}
                y={node.y + 22}
                textAnchor="middle"
                fontSize={12}
                fontFamily="ui-monospace, monospace"
                fontWeight={600}
                fill={fg}
              >
                {label.length > 24 ? `${label.slice(0, 22)}…` : label}
              </text>
              <text
                x={node.x + NODE_W / 2}
                y={node.y + 38}
                textAnchor="middle"
                fontSize={10}
                fill="var(--muted, #888)"
              >
                {sublabel}
              </text>
            </g>
          );

          return href ? (
            <a key={`${node.name}-${node.x}-${node.y}`} href={href}>
              <title>{`${label} - click to view its result page`}</title>
              {content}
            </a>
          ) : (
            <g key={`${node.name}-${node.x}-${node.y}`}>{content}</g>
          );
        })}
      </svg>
    </div>
  );
}
