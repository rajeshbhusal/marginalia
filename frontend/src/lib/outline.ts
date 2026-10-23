import type { Course, OutlineModule, OutlineUpdate } from "../api/types";

// Local editing state for the outline. New items have no id until the server assigns one, so
// every item also gets a `key` for React and for addressing it in actions.

export interface DraftSection {
  key: string;
  id?: string;
  title: string;
  summary: string;
}

export interface DraftModule {
  key: string;
  id?: string;
  title: string;
  summary: string;
  sections: DraftSection[];
}

export interface OutlineDraft {
  title: string;
  description: string;
  modules: DraftModule[];
}

type TextChanges = Partial<Pick<DraftSection, "title" | "summary">>;

/** The keys of every item in a saved outline, in order, to match against the server's reply. */
export type SavedKeys = { module: string; sections: string[] }[];

export type OutlineAction =
  | { type: "reset"; draft: OutlineDraft }
  | { type: "setCourse"; field: "title" | "description"; value: string }
  | { type: "updateModule"; module: string; changes: TextChanges }
  | { type: "updateSection"; module: string; section: string; changes: TextChanges }
  | { type: "addModule" }
  | { type: "removeModule"; module: string }
  | { type: "moveModule"; module: string; by: -1 | 1 }
  | { type: "addSection"; module: string }
  | { type: "removeSection"; module: string; section: string }
  | { type: "moveSection"; module: string; section: string; by: -1 | 1 }
  | { type: "assignIds"; keys: SavedKeys; outline: OutlineModule[] };

let lastKey = 0;
const newKey = () => `new-${++lastKey}`;

export function draftFromCourse(
  course: Pick<Course, "title" | "description" | "outline">,
): OutlineDraft {
  return {
    title: course.title,
    description: course.description,
    modules: course.outline.map((module) => ({
      key: module.id,
      id: module.id,
      title: module.title,
      summary: module.summary,
      sections: module.sections.map((section) => ({
        key: section.id,
        id: section.id,
        title: section.title,
        summary: section.summary,
      })),
    })),
  };
}

function move<T>(items: T[], from: number, to: number): T[] {
  const copy = [...items];
  const [item] = copy.splice(from, 1);
  copy.splice(to, 0, item);
  return copy;
}

function mapModule(
  draft: OutlineDraft,
  key: string,
  update: (module: DraftModule) => DraftModule,
): OutlineDraft {
  return { ...draft, modules: draft.modules.map((m) => (m.key === key ? update(m) : m)) };
}

export function outlineReducer(draft: OutlineDraft, action: OutlineAction): OutlineDraft {
  switch (action.type) {
    case "reset":
      return action.draft;
    case "setCourse":
      return { ...draft, [action.field]: action.value };
    case "updateModule":
      return mapModule(draft, action.module, (m) => ({ ...m, ...action.changes }));
    case "updateSection":
      return mapModule(draft, action.module, (m) => ({
        ...m,
        sections: m.sections.map((s) =>
          s.key === action.section ? { ...s, ...action.changes } : s,
        ),
      }));
    case "addModule":
      return {
        ...draft,
        modules: [
          ...draft.modules,
          {
            key: newKey(),
            title: "New module",
            summary: "",
            sections: [{ key: newKey(), title: "New section", summary: "" }],
          },
        ],
      };
    case "removeModule":
      if (draft.modules.length <= 1) return draft;
      return { ...draft, modules: draft.modules.filter((m) => m.key !== action.module) };
    case "moveModule": {
      const from = draft.modules.findIndex((m) => m.key === action.module);
      const to = from + action.by;
      if (from < 0 || to < 0 || to >= draft.modules.length) return draft;
      return { ...draft, modules: move(draft.modules, from, to) };
    }
    case "addSection":
      return mapModule(draft, action.module, (m) => ({
        ...m,
        sections: [...m.sections, { key: newKey(), title: "New section", summary: "" }],
      }));
    case "removeSection":
      return mapModule(draft, action.module, (m) => ({
        ...m,
        sections: m.sections.filter((s) => s.key !== action.section),
      }));
    case "moveSection":
      return moveSection(draft, action.module, action.section, action.by);
    case "assignIds":
      return assignIds(draft, action.keys, action.outline);
  }
}

export function savedKeys(draft: OutlineDraft): SavedKeys {
  return draft.modules.map((m) => ({ module: m.key, sections: m.sections.map((s) => s.key) }));
}

/**
 * Give new items the ids the server assigned when they were saved. Items are matched by key,
 * not position, so edits made while the save was in flight are kept, and keys never change
 * (an input being typed in keeps its focus).
 */
function assignIds(draft: OutlineDraft, keys: SavedKeys, outline: OutlineModule[]): OutlineDraft {
  const ids = new Map<string, string>();
  keys.forEach((module, i) => {
    const saved = outline[i];
    if (!saved) return;
    ids.set(module.module, saved.id);
    module.sections.forEach((key, j) => {
      if (saved.sections[j]) ids.set(key, saved.sections[j].id);
    });
  });
  return {
    ...draft,
    modules: draft.modules.map((m) => ({
      ...m,
      id: m.id ?? ids.get(m.key),
      sections: m.sections.map((s) => ({ ...s, id: s.id ?? ids.get(s.key) })),
    })),
  };
}

/** Move a section up or down; past either end of its module it moves into the neighbour. */
function moveSection(draft: OutlineDraft, moduleKey: string, sectionKey: string, by: -1 | 1) {
  const moduleIndex = draft.modules.findIndex((m) => m.key === moduleKey);
  const module = draft.modules[moduleIndex];
  const from = module?.sections.findIndex((s) => s.key === sectionKey) ?? -1;
  if (from < 0) return draft;

  const to = from + by;
  if (to >= 0 && to < module.sections.length) {
    return mapModule(draft, moduleKey, (m) => ({ ...m, sections: move(m.sections, from, to) }));
  }
  const neighbour = draft.modules[moduleIndex + by];
  if (!neighbour) return draft;
  const section = module.sections[from];
  const modules = draft.modules.map((m, index) => {
    if (index === moduleIndex) return { ...m, sections: m.sections.filter((_, i) => i !== from) };
    if (index === moduleIndex + by) {
      return {
        ...m,
        sections: by === 1 ? [section, ...m.sections] : [...m.sections, section],
      };
    }
    return m;
  });
  return { ...draft, modules };
}

/** Problems that would stop the outline from being saved, in plain language. */
export function outlineProblems(draft: OutlineDraft): string[] {
  const problems: string[] = [];
  if (!draft.title.trim()) problems.push("Give the course a title.");
  draft.modules.forEach((module, index) => {
    const name = `Module ${index + 1}`;
    if (!module.title.trim()) problems.push(`${name} needs a title.`);
    if (module.sections.length === 0) problems.push(`${name} needs at least one section.`);
    if (module.sections.some((s) => !s.title.trim())) {
      problems.push(`Every section in ${name.toLowerCase()} needs a title.`);
    }
  });
  return problems;
}

export function toOutlineUpdate(draft: OutlineDraft): OutlineUpdate {
  return {
    title: draft.title.trim(),
    description: draft.description.trim(),
    modules: draft.modules.map((module) => ({
      id: module.id,
      title: module.title.trim(),
      summary: module.summary.trim(),
      sections: module.sections.map((section) => ({
        id: section.id,
        title: section.title.trim(),
        summary: section.summary.trim(),
      })),
    })),
  };
}

export function sectionCount(draft: OutlineDraft): number {
  return draft.modules.reduce((total, module) => total + module.sections.length, 0);
}
