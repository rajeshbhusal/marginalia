import { afterEach, describe, expect, it } from "vitest";
import {
  anchorFromSelection,
  collapseWhitespace,
  findQuote,
  offsetOf,
  rangeFromOffsets,
  snapToWords,
  textModel,
} from "./anchoring";

function render(html: string): HTMLElement {
  const container = document.createElement("article");
  container.innerHTML = html;
  document.body.append(container);
  return container;
}

afterEach(() => {
  document.body.innerHTML = "";
  document.getSelection()?.removeAllRanges();
});

describe("findQuote", () => {
  it("finds a unique quote", () => {
    expect(findQuote("Priors meet evidence.", "meet")).toEqual({ start: 7, end: 11 });
  });

  it("uses the prefix and suffix to pick between repeated quotes", () => {
    const text = "The prior matters. A strong prior resists change. A weak prior moves fast.";
    const span = findQuote(text, "prior", "A weak ", " moves");
    expect(span).not.toBeNull();
    expect(text.slice(span!.start - 7, span!.end + 6)).toBe("A weak prior moves");
  });

  it("falls back to ignoring whitespace differences", () => {
    const text = "Base rates\n  matter   a lot.";
    const span = findQuote(text, "rates matter a", "Base ", " lot");
    expect(span).toEqual({ start: 5, end: 23 });
    expect(text.slice(span!.start, span!.end)).toBe("rates\n  matter   a");
  });

  it("returns null when the quote is gone", () => {
    expect(findQuote("Rewritten text", "original passage")).toBeNull();
    expect(findQuote("Anything", "")).toBeNull();
  });
});

describe("snapToWords", () => {
  it("widens a selection that starts or ends mid-word", () => {
    const text = "Back to the question from your diagnostic: a disease affects";
    const start = text.indexOf("estion");
    const end = text.indexOf("ase affects");
    const span = snapToWords(text, { start, end });
    expect(text.slice(span.start, span.end)).toBe("question from your diagnostic: a disease");
  });

  it("leaves whole-word selections alone", () => {
    expect(snapToWords("one two three", { start: 4, end: 7 })).toEqual({ start: 4, end: 7 });
  });
});

describe("collapseWhitespace", () => {
  it("maps collapsed characters back to the original text", () => {
    const { text, map } = collapseWhitespace("a  b\nc");
    expect(text).toBe("a b c");
    expect(map).toEqual([0, 1, 3, 4, 5]);
  });
});

describe("text model and ranges", () => {
  it("skips KaTeX's hidden MathML and interface chrome", () => {
    const root = render(
      `<div data-block-id="b1"><span data-anchor-ignore>Example</span>` +
        `<p>Area is <span class="katex"><span class="katex-mathml">x^2</span>` +
        `<span class="katex-html">x²</span></span> units.</p></div>`,
    );
    expect(textModel(root).text).toBe("Area is x² units.");
  });

  it("builds ranges that span several text nodes", () => {
    const root = render("<p>Hello <strong>bold</strong> world</p>");
    const model = textModel(root);
    const range = rangeFromOffsets(model, findQuote(model.text, "lo bold wo")!);
    expect(range?.toString()).toBe("lo bold wo");
  });

  it("converts element boundary points to text offsets", () => {
    const root = render("<p>One</p><p>Two</p>");
    const model = textModel(root);
    expect(offsetOf(model, root, 1)).toBe(3); // Between the two paragraphs
    expect(offsetOf(model, root.lastChild!.firstChild!, 2)).toBe(5);
  });
});

describe("anchorFromSelection", () => {
  function select(start: Node, startOffset: number, end: Node, endOffset: number) {
    const range = document.createRange();
    range.setStart(start, startOffset);
    range.setEnd(end, endOffset);
    const selection = document.getSelection()!;
    selection.removeAllRanges();
    selection.addRange(range);
    return selection;
  }

  it("describes a selection within one block", () => {
    const container = render(
      `<div data-block-id="b_1"><p>A positive test is weak evidence for a rare disease.</p></div>`,
    );
    const text = container.querySelector("p")!.firstChild!;
    const anchor = anchorFromSelection(select(text, 1, text, 18), container);

    expect(anchor).toMatchObject({
      blockId: "b_1",
      quote: "positive test is",
      prefix: "A ",
      suffix: " weak evidence for a rare diseas",
    });
  });

  it("clips a selection that runs into the next block", () => {
    const container = render(
      `<div data-block-id="b_1"><p>First block text.</p></div>` +
        `<div data-block-id="b_2"><p>Second block.</p></div>`,
    );
    const [first, second] = [...container.querySelectorAll("p")].map((p) => p.firstChild!);
    const anchor = anchorFromSelection(select(first, 6, second, 6), container);

    expect(anchor?.blockId).toBe("b_1");
    expect(anchor?.quote).toBe("block text.");
  });

  it("ignores selections outside the lesson or too short to mean anything", () => {
    const container = render(`<div data-block-id="b_1"><p>Some text</p></div>`);
    const outside = document.createElement("p");
    outside.textContent = "Navigation";
    document.body.append(outside);

    expect(anchorFromSelection(select(outside.firstChild!, 0, outside.firstChild!, 5), container))
      .toBeNull();
    const text = container.querySelector("p")!.firstChild!;
    expect(anchorFromSelection(select(text, 0, text, 1), container)).toBeNull();
  });
});
