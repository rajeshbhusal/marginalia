import { describe, expect, it } from "vitest";
import { layoutMargin } from "./margin";

const item = (id: string, anchor: number, height = 100) => ({ id, anchor, height });

describe("layoutMargin", () => {
  it("puts cards beside their passages when they don't collide", () => {
    const tops = layoutMargin([item("b", 400), item("a", 0)], null);
    expect(Object.fromEntries(tops)).toEqual({ a: 0, b: 400 });
  });

  it("pushes overlapping cards down in reading order", () => {
    const tops = layoutMargin([item("a", 0), item("b", 50), item("c", 60)], null, 10);
    expect(Object.fromEntries(tops)).toEqual({ a: 0, b: 110, c: 220 });
  });

  it("keeps the active card beside its passage and moves earlier cards up", () => {
    const tops = layoutMargin([item("a", 200), item("b", 250), item("c", 260)], "b", 10);
    expect(tops.get("b")).toBe(250);
    expect(tops.get("a")).toBe(140); // Moved up to make room
    expect(tops.get("c")).toBe(360); // Pushed below the active card
  });

  it("falls back to flowing down when there's no room above", () => {
    const tops = layoutMargin([item("a", 0), item("b", 20)], "b", 10);
    expect(Object.fromEntries(tops)).toEqual({ a: 0, b: 110 });
  });
});
