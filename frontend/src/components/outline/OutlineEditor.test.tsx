import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../api/client";
import type { Course } from "../../api/types";
import { OutlineEditor } from "./OutlineEditor";

const LONG_TITLE = "Bootstrapping Segment Loss Ratios in Personal Lines Pricing: A Practical Guide";

const COURSE: Course = {
  id: "c1",
  title: LONG_TITLE,
  description: "Judge whether a segment's loss ratio is reliably better or worse than book average.",
  goal: "Bootstrapping segment loss ratios",
  depth: "practitioner",
  learning_style: "hands_on",
  background: "",
  status: "outline_ready",
  error: null,
  diagnostics: [],
  profile: {
    level: "beginner",
    summary: "Knows how a loss ratio is calculated, but has never used the bootstrap.",
    strengths: ["Loss ratio definition (incurred claims / earned premium)"],
    gaps: ["How a bootstrap resample is constructed (with replacement, same size)"],
  },
  outline: [
    {
      id: "m1",
      title: "What bootstrapping does and why it works",
      summary: "",
      sections: [{ id: "s1", title: "Resampling with replacement, step by step", summary: "" }],
    },
  ],
  sections: [],
  current_section_id: null,
  model: "fake-tutor-1",
  created: "2026-10-27T09:00:00Z",
  updated: "2026-10-27T09:00:00Z",
};

function renderEditor() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <OutlineEditor course={COURSE} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("OutlineEditor", () => {
  beforeEach(() => {
    vi.spyOn(api, "updateOutline").mockResolvedValue(COURSE);
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("edits the title in a wrapping field inside the page heading, so long titles aren't cut off", () => {
    renderEditor();
    const title = screen.getByRole("textbox", { name: "Course title" });
    expect(title.tagName).toBe("TEXTAREA");
    expect(title).toHaveValue(LONG_TITLE);
    expect(screen.getByRole("heading", { level: 1 })).toContainElement(title);
  });

  it("keeps titles on one line", async () => {
    const user = userEvent.setup();
    renderEditor();
    const title = screen.getByRole("textbox", { name: "Course title" });
    await user.type(title, "{Enter}, 2nd edition");
    expect(title).toHaveValue(`${LONG_TITLE}, 2nd edition`);

    const section = screen.getByRole("textbox", { name: "Section 1.1 title" });
    await user.clear(section);
    await user.paste("Resampling\nstep by step");
    expect(section).toHaveValue("Resampling step by step");
  });

  it("lists what the learner knows and still has to learn as wrapping text", () => {
    renderEditor();
    expect(screen.getByText("You already know")).toBeInTheDocument();
    expect(
      screen.getByText("How a bootstrap resample is constructed (with replacement, same size)").tagName,
    ).toBe("SPAN");
  });
});
