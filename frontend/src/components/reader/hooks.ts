import { type RefObject, useCallback, useEffect, useLayoutEffect, useState } from "react";
import {
  anchorFromSelection,
  findQuote,
  rangeFromOffsets,
  type SelectionAnchor,
  textModel,
} from "../../lib/anchoring";

export interface Anchor {
  id: string;
  blockId: string;
  quote: string;
  prefix: string;
  suffix: string;
}

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const media = window.matchMedia(query);
    const update = () => setMatches(media.matches);
    media.addEventListener("change", update);
    update();
    return () => media.removeEventListener("change", update);
  }, [query]);
  return matches;
}

/** A counter that changes whenever the element is resized (content added, diagrams drawn...). */
export function useLayoutVersion(ref: RefObject<HTMLElement | null>): number {
  const [version, setVersion] = useState(0);
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    let frame = 0;
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => setVersion((v) => v + 1));
    });
    observer.observe(element);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [ref]);
  return version;
}

/** The learner's current text selection inside the lesson, as an anchor they can ask about. */
export function useSelectionAnchor(
  containerRef: RefObject<HTMLElement | null>,
  enabled: boolean,
): [SelectionAnchor | null, () => void] {
  const [anchor, setAnchor] = useState<SelectionAnchor | null>(null);

  useEffect(() => {
    if (!enabled) {
      setAnchor(null);
      return;
    }
    let frame = 0;
    const update = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const container = containerRef.current;
        setAnchor(container ? anchorFromSelection(document.getSelection(), container) : null);
      });
    };
    document.addEventListener("selectionchange", update);
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener("selectionchange", update);
      window.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, [containerRef, enabled]);

  const clear = useCallback(() => {
    document.getSelection()?.removeAllRanges();
    setAnchor(null);
  }, []);
  return [anchor, clear];
}

/** Find each anchor's passage in the rendered lesson. Missing passages are left out. */
export function useAnchorRanges(
  containerRef: RefObject<HTMLElement | null>,
  anchors: Anchor[],
  layoutVersion: unknown,
): Map<string, Range> {
  const [ranges, setRanges] = useState<Map<string, Range>>(() => new Map());
  useLayoutEffect(() => {
    const container = containerRef.current;
    const next = new Map<string, Range>();
    for (const anchor of container ? anchors : []) {
      const block = blockElement(container!, anchor.blockId);
      if (!block) continue;
      const model = textModel(block);
      const span = findQuote(model.text, anchor.quote, anchor.prefix, anchor.suffix);
      const range = span ? rangeFromOffsets(model, span) : null;
      if (range) next.set(anchor.id, range);
    }
    setRanges(next);
  }, [containerRef, anchors, layoutVersion]);
  return ranges;
}

export function blockElement(container: HTMLElement, blockId: string): HTMLElement | null {
  return container.querySelector<HTMLElement>(`[data-block-id="${blockId.replace(/"/g, "")}"]`);
}

/** Paint highlighted passages with the CSS Custom Highlight API (no DOM changes needed). */
export function usePaintedHighlights(ranges: Map<string, Range>, activeId: string | null): void {
  useEffect(() => {
    if (typeof CSS === "undefined" || !("highlights" in CSS)) return;
    const normal: Range[] = [];
    const active: Range[] = [];
    for (const [id, range] of ranges) (id === activeId ? active : normal).push(range);
    CSS.highlights.set("marginalia", new Highlight(...normal));
    CSS.highlights.set("marginalia-active", new Highlight(...active));
    return () => {
      CSS.highlights.delete("marginalia");
      CSS.highlights.delete("marginalia-active");
    };
  }, [ranges, activeId]);
}

/** Which highlighted passage, if any, is under the point the learner clicked. */
export function anchorAtPoint(ranges: Map<string, Range>, x: number, y: number): string | null {
  const caret = caretAt(x, y);
  if (!caret) return null;
  for (const [id, range] of ranges) {
    try {
      if (range.isPointInRange(caret.node, caret.offset)) return id;
    } catch {
      // The point is in a different tree than the range
    }
  }
  return null;
}

function caretAt(x: number, y: number): { node: Node; offset: number } | null {
  if ("caretPositionFromPoint" in document) {
    const position = document.caretPositionFromPoint(x, y);
    return position ? { node: position.offsetNode, offset: position.offset } : null;
  }
  const legacy = document as Document & { caretRangeFromPoint?: (x: number, y: number) => Range | null };
  const range = legacy.caretRangeFromPoint?.(x, y);
  return range ? { node: range.startContainer, offset: range.startOffset } : null;
}
