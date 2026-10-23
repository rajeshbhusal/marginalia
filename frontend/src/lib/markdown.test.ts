import { describe, expect, it } from "vitest";
import { normalizeDisplayMath } from "./markdown";

describe("normalizeDisplayMath", () => {
  it("puts single-line display maths fences on their own lines", () => {
    expect(normalizeDisplayMath("Since\n\n$$P(A \\mid B) = 0.5$$\n\nso")).toBe(
      "Since\n\n$$\nP(A \\mid B) = 0.5\n$$\n\nso",
    );
  });

  it("keeps the indentation of maths inside lists", () => {
    expect(normalizeDisplayMath("1. Step\n   $$x = 1$$")).toBe("1. Step\n   $$\n   x = 1\n   $$");
  });

  it("leaves inline maths, fenced maths and code blocks alone", () => {
    const untouched = [
      "where $$x$$ is small",
      "$$\nx^2\n$$",
      "```python\n$$not maths$$\n```",
      "Costs $5 and $$10",
    ];
    for (const text of untouched) expect(normalizeDisplayMath(text)).toBe(text);
  });
});
