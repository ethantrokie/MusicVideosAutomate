import React, { useMemo } from "react";
import {
  AbsoluteFill,
  Img,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import rough from "roughjs";
import { parseSvgGroups, isSimplePath } from "../utils/svgToReact";
import type { ParsedElement } from "../utils/svgToReact";

const SVG_VIEWBOX_WIDTH = 1080;
const SVG_VIEWBOX_HEIGHT = 720;
const CONTAINER_TOP = 600;
const LABEL_TOP = CONTAINER_TOP - 80;
const ENTRANCE_DURATION_FRAMES = 15;
const MIN_DELAY_MS = 800;
const DRAW_DURATION_MS = 500;
const ELEMENT_STAGGER_MS = 150;

// ---------------------------------------------------------------------------
// Rough.js helpers
// ---------------------------------------------------------------------------

const ROUGH_OPTIONS = {
  roughness: 1.5,
  strokeWidth: 2,
};

/**
 * Uses Rough.js to generate an SVG element and returns its outer HTML string.
 * A detached SVG element is used so we never touch the live DOM during render.
 * The resulting HTML is Rough.js-generated geometry (not user-supplied text),
 * so dangerouslySetInnerHTML is safe here.
 */
function roughElementHtml(
  draw: (rc: ReturnType<typeof rough.svg>) => SVGElement,
): string {
  const svgEl = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  const rc = rough.svg(svgEl);
  const node = draw(rc);
  return node.outerHTML;
}

function roughRectHtml(
  x: number,
  y: number,
  w: number,
  h: number,
  stroke: string,
  seed: number,
): string {
  return roughElementHtml((rc) =>
    rc.rectangle(x, y, w, h, { ...ROUGH_OPTIONS, stroke, seed }),
  );
}

function roughCircleHtml(
  cx: number,
  cy: number,
  r: number,
  stroke: string,
  seed: number,
): string {
  return roughElementHtml((rc) =>
    rc.circle(cx, cy, r * 2, { ...ROUGH_OPTIONS, stroke, seed }),
  );
}

function roughEllipseHtml(
  cx: number,
  cy: number,
  rx: number,
  ry: number,
  stroke: string,
  seed: number,
): string {
  return roughElementHtml((rc) =>
    rc.ellipse(cx, cy, rx * 2, ry * 2, { ...ROUGH_OPTIONS, stroke, seed }),
  );
}

function roughLineHtml(
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  stroke: string,
  seed: number,
): string {
  return roughElementHtml((rc) =>
    rc.line(x1, y1, x2, y2, { ...ROUGH_OPTIONS, stroke, seed }),
  );
}

function roughPathHtml(d: string, stroke: string, seed: number): string {
  return roughElementHtml((rc) =>
    rc.path(d, { ...ROUGH_OPTIONS, stroke, seed }),
  );
}

// ---------------------------------------------------------------------------
// Deterministic seed from element id
// ---------------------------------------------------------------------------

function seedFromId(id: string | undefined): number {
  if (!id) return 42;
  let h = 0;
  for (let i = 0; i < id.length; i++) {
    h = (Math.imul(31, h) + id.charCodeAt(i)) | 0;
  }
  return Math.abs(h) || 42;
}

// ---------------------------------------------------------------------------
// Element renderer
// ---------------------------------------------------------------------------

function renderElement(el: ParsedElement, key: string): React.ReactNode {
  const p = el.properties as Record<string, string | number>;
  const stroke = String(p.stroke ?? "#e0e0e0");
  const id = String(p.id ?? key);
  const seed = seedFromId(id);

  switch (el.tagName) {
    case "rect": {
      const x = Number(p.x ?? 0);
      const y = Number(p.y ?? 0);
      const w = Number(p.width ?? 0);
      const h = Number(p.height ?? 0);
      const html = roughRectHtml(x, y, w, h, stroke, seed);
      return (
        <g key={key} dangerouslySetInnerHTML={{ __html: html }} />
      );
    }

    case "circle": {
      const cx = Number(p.cx ?? 0);
      const cy = Number(p.cy ?? 0);
      const r = Number(p.r ?? 0);
      const html = roughCircleHtml(cx, cy, r, stroke, seed);
      return (
        <g key={key} dangerouslySetInnerHTML={{ __html: html }} />
      );
    }

    case "ellipse": {
      const cx = Number(p.cx ?? 0);
      const cy = Number(p.cy ?? 0);
      const rx = Number(p.rx ?? 0);
      const ry = Number(p.ry ?? 0);
      const html = roughEllipseHtml(cx, cy, rx, ry, stroke, seed);
      return (
        <g key={key} dangerouslySetInnerHTML={{ __html: html }} />
      );
    }

    case "line": {
      const x1 = Number(p.x1 ?? 0);
      const y1 = Number(p.y1 ?? 0);
      const x2 = Number(p.x2 ?? 0);
      const y2 = Number(p.y2 ?? 0);
      const html = roughLineHtml(x1, y1, x2, y2, stroke, seed);
      return (
        <g key={key} dangerouslySetInnerHTML={{ __html: html }} />
      );
    }

    case "path": {
      const d = String(p.d ?? "");
      if (isSimplePath(d)) {
        const html = roughPathHtml(d, stroke, seed);
        return (
          <g key={key} dangerouslySetInnerHTML={{ __html: html }} />
        );
      }
      return (
        <path
          key={key}
          d={d}
          stroke={stroke}
          strokeWidth={Number(p["stroke-width"] ?? 2)}
          fill={String(p.fill ?? "none")}
          strokeDasharray="4 2"
        />
      );
    }

    case "text": {
      const x = Number(p.x ?? 0);
      const y = Number(p.y ?? 0);
      return (
        <text
          key={key}
          x={x}
          y={y}
          fill={String(p.fill ?? "#ffffff")}
          fontSize={String(p["font-size"] ?? p.fontSize ?? "16")}
          fontFamily="'Caveat', 'Patrick Hand', cursive, sans-serif"
          textAnchor={String(p["text-anchor"] ?? "start")}
        >
          {el.textContent ?? ""}
          {el.children?.map((child, ci) =>
            renderElement(child, `${key}-tc-${ci}`),
          )}
        </text>
      );
    }

    case "image": {
      const x = Number(p.x ?? 0);
      const y = Number(p.y ?? 0);
      const w = Number(p.width ?? 0);
      const h = Number(p.height ?? 0);
      const href = String(p.href ?? p["xlink:href"] ?? "");
      const src = href.startsWith("http") ? href : staticFile(href);
      return (
        <foreignObject key={key} x={x} y={y} width={w} height={h}>
          <Img
            src={src}
            style={{ width: "100%", height: "100%", objectFit: "contain" }}
          />
        </foreignObject>
      );
    }

    case "polygon":
    case "polyline": {
      const points = String(p.points ?? "");
      const Tag = el.tagName as "polygon" | "polyline";
      return (
        <Tag
          key={key}
          points={points}
          stroke={stroke}
          strokeWidth={Number(p["stroke-width"] ?? 2)}
          fill={String(p.fill ?? "none")}
        />
      );
    }

    case "g": {
      return (
        <g key={key}>
          {el.children?.map((child, ci) =>
            renderElement(child, `${key}-g-${ci}`),
          )}
        </g>
      );
    }

    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// Animated group layer
// ---------------------------------------------------------------------------

const AnimatedGroup: React.FC<{
  children: ParsedElement[];
  groupId: string;
  groupIndex: number;
}> = ({ children, groupId, groupIndex }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const groupRef = React.useRef<SVGSVGElement>(null);

  // Quick entrance opacity (3 frames) to avoid flash of unstyled content
  const entranceFrames = 3;
  const opacity = interpolate(frame, [0, entranceFrames], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Memoize rendered elements — re-render only when group identity changes
  const elements = useMemo(
    () =>
      children.map((child, i) =>
        renderElement(child, `${groupId}-el-${i}`),
      ),
    // groupId and groupIndex uniquely identify this group; children derive from them
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [groupId, groupIndex],
  );

  // Initialize stroke-dasharray on mount so paths start fully hidden
  React.useEffect(() => {
    const svg = groupRef.current;
    if (!svg) return;
    const paths = svg.querySelectorAll("path");
    paths.forEach((path) => {
      const fill = path.getAttribute("fill");
      if (fill && fill !== "none") {
        path.style.opacity = "0";
      } else {
        const length = path.getTotalLength();
        path.style.strokeDasharray = `${length}`;
        path.style.strokeDashoffset = `${length}`;
      }
    });
    const texts = svg.querySelectorAll("text");
    texts.forEach((text) => {
      text.style.opacity = "0";
    });
  }, [groupId, groupIndex]);

  // Animate stroke-dashoffset, fill opacity, and text opacity every frame
  React.useEffect(() => {
    const svg = groupRef.current;
    if (!svg) return;
    const currentTimeMs = (frame / fps) * 1000;
    const paths = svg.querySelectorAll("path");
    let strokePathCount = 0;

    paths.forEach((path, i) => {
      const fill = path.getAttribute("fill");
      if (fill && fill !== "none") {
        // Fill path: fade in after corresponding stroke finishes
        const fillStartMs = i * ELEMENT_STAGGER_MS + DRAW_DURATION_MS + 200;
        const fillDuration = 300;
        const elapsed = currentTimeMs - fillStartMs;
        const fillOpacity = Math.min(Math.max(elapsed / fillDuration, 0), 1);
        path.style.opacity = `${fillOpacity}`;
      } else {
        // Stroke path: animate dashoffset with ease-out curve
        const length = path.getTotalLength();
        const elementStartMs = strokePathCount * ELEMENT_STAGGER_MS;
        const elapsed = currentTimeMs - elementStartMs;
        const progress = Math.min(Math.max(elapsed / DRAW_DURATION_MS, 0), 1);
        const eased = 1 - Math.pow(1 - progress, 2);
        path.style.strokeDashoffset = `${length * (1 - eased)}`;
        strokePathCount++;
      }
    });

    // Text: fade in after all stroke paths finish drawing
    const texts = svg.querySelectorAll("text");
    const lastStrokeStartMs = Math.max(0, strokePathCount - 1) * ELEMENT_STAGGER_MS;
    const textStartMs = lastStrokeStartMs + DRAW_DURATION_MS + 100;
    const textFadeDuration = 300;

    texts.forEach((text) => {
      const elapsed = currentTimeMs - textStartMs;
      const textOpacity = Math.min(Math.max(elapsed / textFadeDuration, 0), 1);
      text.style.opacity = `${textOpacity}`;
    });
  });

  return (
    <svg
      ref={groupRef}
      viewBox={`0 0 ${SVG_VIEWBOX_WIDTH} ${SVG_VIEWBOX_HEIGHT}`}
      width={SVG_VIEWBOX_WIDTH}
      height={SVG_VIEWBOX_HEIGHT}
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        opacity,
        overflow: "visible",
      }}
    >
      {elements}
    </svg>
  );
};

// ---------------------------------------------------------------------------
// ConceptLabel
// ---------------------------------------------------------------------------

const ConceptLabel: React.FC<{ text: string }> = ({ text }) => (
  <div
    style={{
      backgroundColor: "rgba(0, 0, 0, 0.75)",
      borderRadius: 14,
      padding: "8px 20px",
      maxWidth: "88%",
    }}
  >
    <span
      style={{
        color: "#FFFFFF",
        fontSize: 26,
        fontFamily: "SF Pro Display, -apple-system, system-ui, sans-serif",
        fontWeight: 600,
        textAlign: "center",
        lineHeight: 1.3,
      }}
    >
      {text}
    </span>
  </div>
);

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export const EduSvgDiagram: React.FC<{
  svgContent: string;
  concept: string;
}> = ({ svgContent, concept }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const groups = useMemo(() => parseSvgGroups(svgContent), [svgContent]);

  // Calculate entrance frames: enforce minimum 800ms between distinct orders
  const groupFrames = useMemo(() => {
    const result: number[] = [];
    let cumulativeMs = 0;
    let lastOrder = -1;
    let lastCumulativeMs = 0;

    for (let i = 0; i < groups.length; i++) {
      const g = groups[i];
      if (g.order !== lastOrder) {
        // New order tier: apply this group's delay, enforce minimum gap from prev tier
        if (i === 0) {
          cumulativeMs = g.delayMs;
        } else {
          const gap = Math.max(g.delayMs, MIN_DELAY_MS);
          cumulativeMs = lastCumulativeMs + gap;
        }
        lastOrder = g.order;
        lastCumulativeMs = cumulativeMs;
      } else {
        // Same order: share entrance frame with previous group
        cumulativeMs = lastCumulativeMs;
      }
      result.push(Math.round((cumulativeMs / 1000) * fps));
    }
    return result;
  }, [groups, fps]);

  // Concept label appears after all groups have entered
  const lastGroupFrame =
    groupFrames.length > 0
      ? groupFrames[groupFrames.length - 1] + ENTRANCE_DURATION_FRAMES
      : 0;
  const labelStartFrame = lastGroupFrame + Math.round(fps * 0.3);

  const labelOpacity = interpolate(
    frame,
    [labelStartFrame, labelStartFrame + Math.round(fps * 0.4)],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  // Exit fade: last 0.5s of composition duration
  const exitStart = durationInFrames - Math.round(fps * 0.5);
  const exitOpacity = interpolate(
    frame,
    [exitStart, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill style={{ opacity: exitOpacity }}>
      {/* Opaque dark background behind the diagram so stock footage doesn't show through */}
      <div
        style={{
          position: "absolute",
          top: CONTAINER_TOP - 20,
          left: 0,
          width: SVG_VIEWBOX_WIDTH,
          height: SVG_VIEWBOX_HEIGHT + 40,
          backgroundColor: "#1a1a2e",
          borderRadius: 12,
        }}
      />

      {/* SVG diagram container -- centered vertically (720px tall in 1920px frame) */}
      <div
        style={{
          position: "absolute",
          top: CONTAINER_TOP,
          left: 0,
          width: SVG_VIEWBOX_WIDTH,
          height: SVG_VIEWBOX_HEIGHT,
        }}
      >
        {groups.map((group, i) => (
          <Sequence
            key={`svg-group-${group.id}`}
            from={groupFrames[i]}
            layout="none"
          >
            <AnimatedGroup
              children={group.children}
              groupId={group.id}
              groupIndex={i}
            />
          </Sequence>
        ))}
      </div>

      {/* Concept label positioned above the SVG container */}
      {concept && (
        <div
          style={{
            position: "absolute",
            top: LABEL_TOP,
            left: 0,
            right: 0,
            display: "flex",
            justifyContent: "center",
            opacity: labelOpacity,
          }}
        >
          <ConceptLabel text={concept} />
        </div>
      )}
    </AbsoluteFill>
  );
};
