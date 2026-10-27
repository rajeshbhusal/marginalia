import { describe, expect, it } from "vitest";
import {
  draftFromCourse,
  type OutlineDraft,
  outlineProblems,
  outlineReducer,
  savedKeys,
  sectionCount,
  toOutlineUpdate,
} from "./outline";

const draft: OutlineDraft = draftFromCourse({
  title: "Bayes",
  description: "A course",
  outline: [
    {
      id: "m1",
      title: "Foundations",
      summary: "",
      sections: [
        { id: "s1", title: "Beliefs", summary: "" },
        { id: "s2", title: "Conditioning", summary: "" },
      ],
    },
    { id: "m2", title: "Bayes' theorem", summary: "", sections: [{ id: "s3", title: "Derivation", summary: "" }] },
  ],
});

const titles = (outline: OutlineDraft) => outline.modules.map((m) => m.sections.map((s) => s.title));

describe("outlineReducer", () => {
  it("renames sections and modules without touching anything else", () => {
    let next = outlineReducer(draft, {
      type: "updateSection",
      module: "m1",
      section: "s2",
      changes: { title: "Conditional probability" },
    });
    next = outlineReducer(next, { type: "updateModule", module: "m2", changes: { title: "Bayes" } });

    expect(titles(next)).toEqual([["Beliefs", "Conditional probability"], ["Derivation"]]);
    expect(next.modules[1].title).toBe("Bayes");
    expect(draft.modules[0].sections[1].title).toBe("Conditioning"); // Not mutated
  });

  it("moves sections within a module and across module boundaries", () => {
    const swapped = outlineReducer(draft, { type: "moveSection", module: "m1", section: "s2", by: -1 });
    expect(titles(swapped)).toEqual([["Conditioning", "Beliefs"], ["Derivation"]]);

    const down = outlineReducer(draft, { type: "moveSection", module: "m1", section: "s2", by: 1 });
    expect(titles(down)).toEqual([["Beliefs"], ["Conditioning", "Derivation"]]);

    const up = outlineReducer(draft, { type: "moveSection", module: "m2", section: "s3", by: -1 });
    expect(titles(up)).toEqual([["Beliefs", "Conditioning", "Derivation"], []]);

    const stuck = outlineReducer(draft, { type: "moveSection", module: "m1", section: "s1", by: -1 });
    expect(stuck).toBe(draft);
  });

  it("adds and removes items, keeping at least one module", () => {
    let next = outlineReducer(draft, { type: "addSection", module: "m2" });
    next = outlineReducer(next, { type: "addModule" });
    expect(sectionCount(next)).toBe(5);
    expect(next.modules[2].sections[0].id).toBeUndefined();

    next = outlineReducer(next, { type: "removeModule", module: "m1" });
    next = outlineReducer(next, { type: "removeModule", module: "m2" });
    expect(next.modules).toHaveLength(1);
    expect(outlineReducer(next, { type: "removeModule", module: next.modules[0].key })).toBe(next);
  });

  it("reorders modules", () => {
    const next = outlineReducer(draft, { type: "moveModule", module: "m2", by: -1 });
    expect(next.modules.map((m) => m.id)).toEqual(["m2", "m1"]);
  });
});

describe("validation and saving", () => {
  it("explains what needs fixing", () => {
    let broken = outlineReducer(draft, { type: "setCourse", field: "title", value: "  " });
    broken = outlineReducer(broken, { type: "removeSection", module: "m2", section: "s3" });
    broken = outlineReducer(broken, {
      type: "updateSection",
      module: "m1",
      section: "s1",
      changes: { title: "" },
    });
    expect(outlineProblems(broken)).toEqual([
      "Give the course a title.",
      "Every section in module 1 needs a title.",
      "Module 2 needs at least one section.",
    ]);
    expect(outlineProblems(draft)).toEqual([]);
  });

  it("builds the API payload with trimmed text and existing ids", () => {
    const edited = outlineReducer(draft, { type: "setCourse", field: "title", value: "  Bayes 101 " });
    const payload = toOutlineUpdate(outlineReducer(edited, { type: "addSection", module: "m1" }));
    expect(payload.title).toBe("Bayes 101");
    expect(payload.modules[0].sections.map((s) => s.id)).toEqual(["s1", "s2", undefined]);
  });
});

describe("assignIds", () => {
  it("gives new items the server's ids without changing their keys", () => {
    const withNew = outlineReducer(draft, { type: "addSection", module: "m2" });
    const keys = savedKeys(withNew);
    const newKey = withNew.modules[1].sections[1].key;
    // The learner keeps typing in the new section while the save is in flight
    const typed = outlineReducer(withNew, {
      type: "updateSection",
      module: "m2",
      section: newKey,
      changes: { title: "Odds form" },
    });
    const server = [
      { id: "m1", title: "", summary: "", sections: [{ id: "s1", title: "", summary: "" }, { id: "s2", title: "", summary: "" }] },
      { id: "m2", title: "", summary: "", sections: [{ id: "s3", title: "", summary: "" }, { id: "s9", title: "", summary: "" }] },
    ];

    const next = outlineReducer(typed, { type: "assignIds", keys, outline: server });

    const added = next.modules[1].sections[1];
    expect(added).toMatchObject({ key: newKey, id: "s9", title: "Odds form" });
  });
});

