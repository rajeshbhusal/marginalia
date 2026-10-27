/**
 * Text anchoring for highlight-and-ask.
 *
 * A thread stores the highlighted text (the quote) plus a little text either side of it (prefix
 * and suffix), like the W3C TextQuoteSelector. To show the highlight again we search the block's
 * rendered text for the quote, preferring the occurrence whose surroundings match best. This
 * survives re-renders, unlike DOM offsets, and needs nothing from the server but the block id.
 */

// Rendered text that isn't part of the passage a reader sees: KaTeX's hidden MathML copy of
// each formula, and interface chrome such as labels and buttons.
const IGNORED = ".katex-mathml, [data-anchor-ignore]";

export const CONTEXT_LENGTH = 32;
export const MAX_QUOTE_LENGTH = 1000;

export interface TextModel {
  text: string;
  nodes: { node: Text; start: number }[];
}

export interface TextSpan {
  start: number;
  end: number;
}

export interface SelectionAnchor {
  blockId: string;
  quote: string;
  prefix: string;
  suffix: string;
  rect: DOMRect;
}

/** The visible text under `root`, with where each text node starts in it. */
export function textModel(root: Node): TextModel {
  const nodes: TextModel["nodes"] = [];
  let text = "";
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: (node) =>
      node.parentElement?.closest(IGNORED) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT,
  });
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const textNode = node as Text;
    nodes.push({ node: textNode, start: text.length });
    text += textNode.data;
  }
  return { text, nodes };
}

/** Convert a DOM boundary point (as in a Range) to a character offset in the text model. */
export function offsetOf(model: TextModel, container: Node, offset: number): number {
  for (const { node, start } of model.nodes) {
    if (node === container) return start + Math.min(offset, node.data.length);
  }
  // The point is between elements or inside ignored text: count the text that comes before it
  const point = document.createRange();
  point.setStart(container, offset);
  let count = 0;
  for (const { node, start } of model.nodes) {
    if (point.comparePoint(node, 0) >= 0) break;
    count = start + node.data.length;
  }
  return count;
}

/** A DOM Range covering characters [start, end) of the text model. */
export function rangeFromOffsets(model: TextModel, { start, end }: TextSpan): Range | null {
  const startPoint = pointAt(model, start, "start");
  const endPoint = pointAt(model, end, "end");
  if (!startPoint || !endPoint) return null;
  const range = document.createRange();
  range.setStart(...startPoint);
  range.setEnd(...endPoint);
  return range;
}

function pointAt(model: TextModel, offset: number, edge: "start" | "end"): [Text, number] | null {
  for (const { node, start } of model.nodes) {
    const end = start + node.data.length;
    // A start offset at a node boundary belongs to the next node, an end offset to this one
    if (offset >= start && (offset < end || (edge === "end" && offset === end))) {
      return [node, offset - start];
    }
  }
  return null;
}

/** Find the quote in `text`, using the prefix and suffix to choose between repeats. */
export function findQuote(text: string, quote: string, prefix = "", suffix = ""): TextSpan | null {
  const exact = bestOccurrence(text, quote, prefix, suffix);
  if (exact) return exact;

  // Whitespace can differ between renders (line breaks, nested elements): ignore it and retry
  const collapsed = collapseWhitespace(text);
  const found = bestOccurrence(
    collapsed.text,
    collapseWhitespace(quote).text.trim(),
    collapseWhitespace(prefix).text,
    collapseWhitespace(suffix).text,
  );
  if (!found) return null;
  return { start: collapsed.map[found.start], end: collapsed.map[found.end - 1] + 1 };
}

function bestOccurrence(
  text: string,
  quote: string,
  prefix: string,
  suffix: string,
): TextSpan | null {
  if (!quote) return null;
  let best: TextSpan | null = null;
  let bestScore = -1;
  for (let i = text.indexOf(quote); i !== -1; i = text.indexOf(quote, i + 1)) {
    const end = i + quote.length;
    const score =
      sharedSuffixLength(text.slice(Math.max(0, i - prefix.length), i), prefix) +
      sharedPrefixLength(text.slice(end, end + suffix.length), suffix);
    if (score > bestScore) {
      best = { start: i, end };
      bestScore = score;
    }
  }
  return best;
}

function sharedPrefixLength(a: string, b: string): number {
  let n = 0;
  while (n < a.length && n < b.length && a[n] === b[n]) n++;
  return n;
}

function sharedSuffixLength(a: string, b: string): number {
  let n = 0;
  while (n < a.length && n < b.length && a[a.length - 1 - n] === b[b.length - 1 - n]) n++;
  return n;
}

/** Collapse runs of whitespace to one space, remembering where each character came from. */
export function collapseWhitespace(text: string): { text: string; map: number[] } {
  let out = "";
  const map: number[] = [];
  for (let i = 0; i < text.length; i++) {
    const isSpace = /\s/.test(text[i]);
    if (isSpace && out.endsWith(" ")) continue;
    out += isSpace ? " " : text[i];
    map.push(i);
  }
  return { text: out, map };
}

const WORD_CHARACTER = /[\p{L}\p{N}]/u;
const MAX_SNAP = 40;

/** Widen a span that starts or ends mid-word to cover the whole words. */
export function snapToWords(text: string, { start, end }: TextSpan): TextSpan {
  const isWord = (i: number) => i >= 0 && i < text.length && WORD_CHARACTER.test(text[i]);
  for (let n = 0; n < MAX_SNAP && isWord(start - 1) && isWord(start); n++) start--;
  for (let n = 0; n < MAX_SNAP && isWord(end) && isWord(end - 1); n++) end++;
  return { start, end };
}

/** The block element ([data-block-id]) that contains a node, if any. */
export function blockElementOf(node: Node | null): HTMLElement | null {
  const element = node instanceof Element ? node : (node?.parentElement ?? null);
  return element?.closest<HTMLElement>("[data-block-id]") ?? null;
}

/**
 * Describe the current selection as an anchor: which block it's in, the quote and its context.
 * A selection that spills over into later blocks is clipped to the block where it starts.
 */
export function anchorFromSelection(
  selection: Selection | null,
  container: HTMLElement,
): SelectionAnchor | null {
  if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return null;
  const range = selection.getRangeAt(0);
  const block = blockElementOf(range.startContainer);
  if (!block?.dataset.blockId || !container.contains(block)) return null;

  const model = textModel(block);
  let start = offsetOf(model, range.startContainer, range.startOffset);
  let end = block.contains(range.endContainer)
    ? offsetOf(model, range.endContainer, range.endOffset)
    : model.text.length;
  while (start < end && /\s/.test(model.text[start])) start++;
  while (end > start && /\s/.test(model.text[end - 1])) end--;
  if (end - start < 2) return null; // Ignore stray clicks and single characters
  ({ start, end } = snapToWords(model.text, { start, end }));
  end = Math.min(end, start + MAX_QUOTE_LENGTH);

  return {
    blockId: block.dataset.blockId,
    quote: model.text.slice(start, end),
    prefix: model.text.slice(Math.max(0, start - CONTEXT_LENGTH), start),
    suffix: model.text.slice(end, end + CONTEXT_LENGTH),
    // jsdom (used in tests) has no layout, so getBoundingClientRect may be missing there
    rect:
      typeof range.getBoundingClientRect === "function"
        ? range.getBoundingClientRect()
        : new DOMRect(),
  };
}
