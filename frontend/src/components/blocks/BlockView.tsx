import clsx from "clsx";
import {
  BookOpen,
  CircleCheck,
  FlaskConical,
  KeyRound,
  Lightbulb,
  PencilLine,
  TriangleAlert,
} from "lucide-react";
import { useState } from "react";
import type { Block, CalloutBlock, ExampleBlock, ExerciseBlock } from "../../api/types";
import { CodeBlock } from "../markdown/CodeBlock";
import { Markdown } from "../markdown/Markdown";
import { MermaidDiagram } from "../markdown/MermaidDiagram";
import { Button } from "../ui";

export function BlockView({ block }: { block: Block }) {
  switch (block.type) {
    case "text":
      return <Markdown>{block.markdown}</Markdown>;
    case "code":
      return <CodeBlock language={block.language} code={block.code} caption={block.caption} />;
    case "diagram":
      return <MermaidDiagram code={block.mermaid} caption={block.caption} />;
    case "example":
      return <ExampleView block={block} />;
    case "exercise":
      return <ExerciseView block={block} />;
    case "callout":
      return <CalloutView block={block} />;
  }
}

function Label({ icon: Icon, children }: { icon: typeof Lightbulb; children: string }) {
  return (
    <div
      className="mb-2 flex items-center gap-2 font-sans text-sm font-medium text-ink-muted"
      data-anchor-ignore
    >
      <Icon className="size-4" aria-hidden />
      {children}
    </div>
  );
}

function ExampleView({ block }: { block: ExampleBlock }) {
  return (
    <div className="rounded-xl border border-line bg-sunken px-5 py-4">
      <Label icon={FlaskConical}>Worked example</Label>
      <h3 className="mb-2 font-sans text-base font-semibold text-ink">{block.title}</h3>
      <Markdown>{block.markdown}</Markdown>
    </div>
  );
}

function ExerciseView({ block }: { block: ExerciseBlock }) {
  const [hintsShown, setHintsShown] = useState(0);
  const [solutionShown, setSolutionShown] = useState(false);

  return (
    <div className="rounded-xl border border-dashed border-line-strong px-5 py-4">
      <Label icon={PencilLine}>Try it</Label>
      <Markdown>{block.prompt}</Markdown>
      {block.hints.slice(0, hintsShown).map((hint, index) => (
        <div key={index} className="mt-3 rounded-lg bg-sunken px-4 py-3">
          <span className="font-sans text-xs font-semibold text-ink-subtle" data-anchor-ignore>
            Hint {index + 1}
          </span>
          <Markdown compact>{hint}</Markdown>
        </div>
      ))}
      <div className="mt-4 flex flex-wrap gap-2" data-anchor-ignore>
        {hintsShown < block.hints.length && (
          <Button variant="secondary" size="sm" onClick={() => setHintsShown((n) => n + 1)}>
            Show a hint ({hintsShown + 1} of {block.hints.length})
          </Button>
        )}
        <Button variant="ghost" size="sm" onClick={() => setSolutionShown((shown) => !shown)}>
          {solutionShown ? "Hide solution" : "Show solution"}
        </Button>
      </div>
      {solutionShown && (
        <div className="mt-4 border-t border-line pt-4">
          <Label icon={CircleCheck}>Solution</Label>
          <Markdown>{block.solution}</Markdown>
        </div>
      )}
    </div>
  );
}

// Colour only where it means something: the accent for the key idea, amber for a warning
const CALLOUTS = {
  key_idea: { icon: KeyRound, label: "Key idea", tone: "border-brand bg-brand-soft", iconTone: "text-brand-ink" },
  definition: { icon: BookOpen, label: "Definition", tone: "border-line-strong bg-sunken", iconTone: "text-ink-muted" },
  tip: { icon: Lightbulb, label: "Tip", tone: "border-line-strong bg-sunken", iconTone: "text-ink-muted" },
  warning: { icon: TriangleAlert, label: "Watch out", tone: "border-warning bg-warning-soft", iconTone: "text-warning-ink" },
} as const;

function CalloutView({ block }: { block: CalloutBlock }) {
  const style = CALLOUTS[block.variant] ?? CALLOUTS.key_idea;
  const Icon = style.icon;
  return (
    <aside className={clsx("rounded-r-xl border-l-4 px-5 py-4", style.tone)}>
      <div className="mb-2 flex items-center gap-2 font-sans text-sm font-semibold text-ink">
        <Icon className={clsx("size-4 shrink-0", style.iconTone)} aria-hidden />
        <span>{block.title || style.label}</span>
      </div>
      <Markdown>{block.markdown}</Markdown>
    </aside>
  );
}
