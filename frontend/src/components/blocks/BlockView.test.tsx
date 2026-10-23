import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { BlockView } from "./BlockView";

describe("BlockView", () => {
  it("renders markdown with maths through KaTeX", () => {
    const { container } = render(
      <BlockView block={{ id: "b1", type: "text", markdown: "Area is $\\pi r^2$, **exactly**." }} />,
    );
    expect(container.querySelector(".katex")).not.toBeNull();
    expect(screen.getByText("exactly").tagName).toBe("STRONG");
  });

  it("reveals exercise hints one at a time, then the solution", async () => {
    const user = userEvent.setup();
    render(
      <BlockView
        block={{
          id: "b2",
          type: "exercise",
          prompt: "What is 2 + 2?",
          hints: ["Count on your fingers.", "It's even."],
          solution: "The answer is 4.",
        }}
      />,
    );
    expect(screen.queryByText("Count on your fingers.")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Show a hint (1 of 2)" }));
    expect(screen.getByText("Count on your fingers.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Show a hint (2 of 2)" }));
    expect(screen.queryByRole("button", { name: /Show a hint/ })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Show solution" }));
    expect(screen.getByText("The answer is 4.")).toBeInTheDocument();
  });

  it("labels callouts by variant when they have no title", () => {
    render(
      <BlockView
        block={{ id: "b3", type: "callout", variant: "warning", title: "", markdown: "Careful." }}
      />,
    );
    expect(screen.getByText("Watch out")).toBeInTheDocument();
  });

  it("marks interface labels so they can't end up in a highlighted quote", () => {
    const { container } = render(
      <BlockView block={{ id: "b4", type: "example", title: "A case", markdown: "Step one." }} />,
    );
    expect(container.querySelector("[data-anchor-ignore]")?.textContent).toBe("Worked example");
  });
});
