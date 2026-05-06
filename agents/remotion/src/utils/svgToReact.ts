import { parse, ElementNode, Node } from 'svg-parser';

export interface ParsedElement {
  tagName: string;
  properties: Record<string, string | number>;
  children?: ParsedElement[];
  textContent?: string;
}

export interface SvgGroup {
  id: string;
  order: number;
  delayMs: number;
  children: ParsedElement[];
}

/**
 * Returns true if the SVG path `d` attribute is suitable for Rough.js rendering.
 * Simple = fewer than 500 characters AND no cubic Bezier commands (C or c).
 * Quadratic (Q, q) and arc (A, a) commands are permitted.
 */
export function isSimplePath(d: string): boolean {
  if (d.length >= 500) {
    return false;
  }
  return !/[Cc]/.test(d);
}

/**
 * Recursively converts a parsed svg-parser Node into a ParsedElement.
 * Returns null for text nodes that have no meaningful content or for
 * elements with no tagName.
 */
function nodeToElement(node: Node | string): ParsedElement | null {
  if (typeof node === 'string') {
    return null;
  }

  if (node.type === 'text') {
    return null;
  }

  const el = node as ElementNode;

  if (!el.tagName) {
    return null;
  }

  const properties: Record<string, string | number> = { ...(el.properties ?? {}) };

  let textContent: string | undefined;
  const childElements: ParsedElement[] = [];

  for (const child of el.children) {
    if (typeof child === 'string') {
      const trimmed = child.trim();
      if (trimmed.length > 0) {
        textContent = trimmed;
      }
      continue;
    }

    if (child.type === 'text') {
      const val = child.value;
      if (val !== undefined && val !== null) {
        const text = String(val).trim();
        if (text.length > 0) {
          textContent = text;
        }
      }
      continue;
    }

    const parsed = nodeToElement(child);
    if (parsed !== null) {
      childElements.push(parsed);
    }
  }

  const result: ParsedElement = {
    tagName: el.tagName,
    properties,
  };

  if (childElements.length > 0) {
    result.children = childElements;
  }

  if (textContent !== undefined) {
    result.textContent = textContent;
  }

  return result;
}

/**
 * Walks the parsed SVG tree and collects all `<g>` elements that carry a
 * `data-order` property, regardless of nesting depth.
 */
function collectGroups(
  nodes: Array<Node | string>,
  accumulator: Array<{ node: ElementNode; docOrder: number }>,
  counter: { value: number },
): void {
  for (const node of nodes) {
    if (typeof node === 'string') {
      continue;
    }

    if (node.type !== 'element') {
      continue;
    }

    const el = node as ElementNode;
    counter.value += 1;

    const props = el.properties ?? {};
    const hasDataOrder =
      'data-order' in props ||
      'dataOrder' in props;

    if (el.tagName === 'g' && hasDataOrder) {
      accumulator.push({ node: el, docOrder: counter.value });
    }

    if (el.children && el.children.length > 0) {
      collectGroups(el.children, accumulator, counter);
    }
  }
}

/**
 * Parses an SVG string and returns all animated groups sorted by their
 * `data-order` attribute. Document order is preserved for ties (stable sort).
 */
export function parseSvgGroups(svgContent: string): SvgGroup[] {
  const root = parse(svgContent);

  const rawGroups: Array<{ node: ElementNode; docOrder: number }> = [];
  const counter = { value: 0 };

  collectGroups(root.children, rawGroups, counter);

  const groups: SvgGroup[] = rawGroups.map(({ node, docOrder }) => {
    const props = node.properties ?? {};

    // Support both `data-order` (HTML attribute style) and `dataOrder` (camelCase)
    const rawOrder = props['data-order'] ?? props['dataOrder'] ?? 0;
    const order = typeof rawOrder === 'number' ? rawOrder : parseInt(String(rawOrder), 10);

    const rawDelay = props['data-delay-ms'] ?? props['dataDelayMs'] ?? 0;
    const delayMs = typeof rawDelay === 'number' ? rawDelay : parseInt(String(rawDelay), 10);

    const rawId = props['id'] ?? props['data-id'] ?? `group-${docOrder}`;
    const id = String(rawId);

    const childElements: ParsedElement[] = [];
    for (const child of node.children) {
      const parsed = nodeToElement(child);
      if (parsed !== null) {
        childElements.push(parsed);
      }
    }

    return {
      id,
      order: isNaN(order) ? 0 : order,
      delayMs: isNaN(delayMs) ? 0 : delayMs,
      children: childElements,
    };
  });

  // Stable sort: primary key is `order`, secondary key is original index (docOrder
  // is monotonically increasing so comparing indices achieves document-order stability).
  return groups
    .map((g, index) => ({ g, index }))
    .sort((a, b) => {
      const diff = a.g.order - b.g.order;
      return diff !== 0 ? diff : a.index - b.index;
    })
    .map(({ g }) => g);
}
