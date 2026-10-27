import type { Depth, LearningStyle, SectionStage } from "../api/types";

export const DEPTHS: { value: Depth; label: string; description: string }[] = [
  {
    value: "overview",
    label: "Overview",
    description: "The big picture and key intuitions, in plain language.",
  },
  {
    value: "practitioner",
    label: "Practitioner",
    description: "Enough depth to use it: techniques, examples and pitfalls.",
  },
  {
    value: "rigorous",
    label: "Rigorous",
    description: "Formal definitions, derivations and challenging exercises.",
  },
];

export const STYLES: { value: LearningStyle; label: string; description: string }[] = [
  { value: "visual", label: "Visual", description: "Diagrams, tables and pictures first." },
  { value: "reading", label: "Reading", description: "Clear, well-structured explanations." },
  { value: "hands_on", label: "Hands-on", description: "Examples, code and practice." },
  { value: "intuition", label: "Intuition first", description: "Analogies before formalism." },
];

export const depthLabel = (depth: Depth) => DEPTHS.find((d) => d.value === depth)?.label ?? depth;
export const styleLabel = (style: LearningStyle) =>
  STYLES.find((s) => s.value === style)?.label ?? style;

export const STAGE_LABELS: Record<SectionStage, string> = {
  queued: "Getting started",
  researching: "Researching sources",
  writing: "Writing",
};

export function plural(count: number, word: string, pluralWord = `${word}s`): string {
  return `${count} ${count === 1 ? word : pluralWord}`;
}
