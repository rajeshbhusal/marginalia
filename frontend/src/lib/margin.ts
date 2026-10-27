export interface MarginItem {
  id: string;
  anchor: number; // Where the item's passage starts, in the margin's coordinates
  height: number;
}

/**
 * Place margin cards next to their passages without overlapping, like comments in a document
 * editor. The active card sits exactly beside its passage; cards after it are pushed down and
 * cards before it are pushed up. If pushing up would run past the top, everything flows down.
 */
export function layoutMargin(
  items: MarginItem[],
  activeId: string | null,
  gap = 12,
): Map<string, number> {
  const sorted = [...items].sort((a, b) => a.anchor - b.anchor);
  const pivot = activeId ? sorted.findIndex((item) => item.id === activeId) : -1;
  if (pivot > 0) {
    const tops = new Map<string, number>();
    const active = sorted[pivot];
    tops.set(active.id, active.anchor);
    flowDown(sorted.slice(pivot + 1), active.anchor + active.height + gap, gap, tops);
    let limit = active.anchor - gap;
    for (const item of sorted.slice(0, pivot).reverse()) {
      const top = Math.min(item.anchor, limit - item.height);
      tops.set(item.id, top);
      limit = top - gap;
    }
    if (Math.min(...tops.values()) >= 0) return tops;
  }
  return flowDown(sorted, -Infinity, gap, new Map());
}

function flowDown(items: MarginItem[], start: number, gap: number, tops: Map<string, number>) {
  let next = start;
  for (const item of items) {
    const top = Math.max(item.anchor, next);
    tops.set(item.id, top);
    next = top + item.height + gap;
  }
  return tops;
}
