import { MessageSquarePlus, X } from "lucide-react";
import {
  type ReactNode,
  type RefObject,
  useCallback,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import type { SelectionAnchor } from "../../lib/anchoring";
import { layoutMargin } from "../../lib/margin";
import { Button, IconButton } from "../ui";
import { blockElement } from "./hooks";

export interface MarginEntry {
  id: string;
  blockId: string;
  node: ReactNode;
}

const ESTIMATED_CARD_HEIGHT = 140;

/** Desktop margin: each card sits beside its passage, nudged so cards never overlap. */
export function MarginColumn({
  entries,
  ranges,
  activeId,
  articleRef,
  layoutVersion,
}: {
  entries: MarginEntry[];
  ranges: Map<string, Range>;
  activeId: string | null;
  articleRef: RefObject<HTMLElement | null>;
  layoutVersion: number;
}) {
  const columnRef = useRef<HTMLDivElement>(null);
  const [anchors, setAnchors] = useState<Map<string, number>>(() => new Map());
  const [heights, setHeights] = useState<Record<string, number>>({});

  useLayoutEffect(() => {
    const column = columnRef.current;
    const article = articleRef.current;
    if (!column || !article) return;
    const base = column.getBoundingClientRect().top;
    const next = new Map<string, number>();
    for (const entry of entries) {
      const rect =
        ranges.get(entry.id)?.getBoundingClientRect() ??
        blockElement(article, entry.blockId)?.getBoundingClientRect();
      if (rect) next.set(entry.id, rect.top - base);
    }
    setAnchors(next);
  }, [entries, ranges, layoutVersion, articleRef]);

  const reportHeight = useCallback((id: string, height: number) => {
    setHeights((current) => (current[id] === height ? current : { ...current, [id]: height }));
  }, []);

  const placed = entries.filter((entry) => anchors.has(entry.id));
  const tops = layoutMargin(
    placed.map((entry) => ({
      id: entry.id,
      anchor: anchors.get(entry.id)!,
      height: heights[entry.id] ?? ESTIMATED_CARD_HEIGHT,
    })),
    activeId,
  );
  const bottom = Math.max(
    0,
    ...placed.map((e) => (tops.get(e.id) ?? 0) + (heights[e.id] ?? ESTIMATED_CARD_HEIGHT)),
  );

  return (
    <div ref={columnRef} className="relative" style={{ minHeight: bottom }}>
      {placed.map((entry) => (
        <PlacedCard key={entry.id} id={entry.id} top={tops.get(entry.id) ?? 0} onHeight={reportHeight}>
          {entry.node}
        </PlacedCard>
      ))}
    </div>
  );
}

function PlacedCard({
  id,
  top,
  onHeight,
  children,
}: {
  id: string;
  top: number;
  onHeight: (id: string, height: number) => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;
    onHeight(id, element.offsetHeight);
    const observer = new ResizeObserver(() => onHeight(id, element.offsetHeight));
    observer.observe(element);
    return () => observer.disconnect();
  }, [id, onHeight]);
  return (
    <div
      ref={ref}
      className="absolute inset-x-0 transition-[top] duration-200 ease-out"
      style={{ top }}
    >
      {children}
    </div>
  );
}

/** Mobile margin: threads in a bottom sheet. */
export function MarginSheet({
  open,
  onClose,
  children,
}: {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40" role="dialog" aria-modal="true" aria-label="Margin notes">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="absolute inset-x-0 bottom-0 max-h-[78dvh] overflow-y-auto rounded-t-2xl border-t border-line bg-bg px-4 pt-3 pb-8 shadow-2xl">
        <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-line-strong" />
        <div className="mb-3 flex items-center justify-between">
          <p className="font-medium text-ink">Margin notes</p>
          <IconButton label="Close" onClick={onClose}>
            <X className="size-4" />
          </IconButton>
        </div>
        <div className="space-y-3">{children}</div>
      </div>
    </div>
  );
}

/** The button that appears when the learner selects text. */
export function AskButton({
  anchor,
  onAsk,
  docked,
}: {
  anchor: SelectionAnchor;
  onAsk: () => void;
  docked: boolean; // Pin to the bottom of the screen (phones), clear of the system selection menu
}) {
  // Keep the selection while clicking: a mousedown would otherwise clear it first
  const keepSelection = (event: React.MouseEvent) => event.preventDefault();
  if (docked) {
    return (
      <div className="fixed inset-x-0 bottom-5 z-40 flex justify-center px-4">
        <Button size="lg" className="shadow-lg" onMouseDown={keepSelection} onClick={onAsk}>
          <MessageSquarePlus className="size-4" aria-hidden />
          Ask about this passage
        </Button>
      </div>
    );
  }
  const top = Math.max(anchor.rect.top - 46, 64);
  const left = Math.min(Math.max(anchor.rect.left + anchor.rect.width / 2, 70), window.innerWidth - 70);
  return (
    <div className="fixed z-40 -translate-x-1/2" style={{ top, left }}>
      <Button size="sm" className="shadow-lg" onMouseDown={keepSelection} onClick={onAsk}>
        <MessageSquarePlus className="size-4" aria-hidden />
        Ask
      </Button>
    </div>
  );
}
