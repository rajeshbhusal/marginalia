import clsx from "clsx";
import { BookOpen, FlaskConical, Lightbulb, PencilLine, Sparkles, TriangleAlert } from "lucide-react";
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
      className="mb-2 flex items-center gap-1.5 font-sans text-xs font-semibold tracking-wide text-ink-3 uppercase"
      data-anchor-ignore
    >
      <Icon className="size-3.5" aria-hidden />
      {children}
    </div>
  );
}

function ExampleView({ block }: { block: ExampleBlock }) {
  return (
    <div className="rounded-xl border border-line bg-surface-2/70 px-5 py-4">
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
        <div key={index} className="mt-3 rounded-lg bg-surface-2 px-4 py-2.5">
          <span className="font-sans text-xs font-semibold text-ink-3" data-anchor-ignore>
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
          <Label icon={Sparkles}>Solution</Label>
          <Markdown>{block.solution}</Markdown>
        </div>
      )}
    </div>
  );
}

const CALLOUTS = {
  key_idea: { icon: Lightbulb, label: "Key idea", tone: "border-accent bg-accent-soft/60" },
  definition: { icon: BookOpen, label: "Definition", tone: "border-ink-3 bg-surface-2/70" },
  tip: { icon: Sparkles, label: "Tip", tone: "border-success bg-success-soft/70" },
  warning: { icon: TriangleAlert, label: "Watch out", tone: "border-warning bg-warning-soft/70" },
} as const;

function CalloutView({ block }: { block: CalloutBlock }) {
  const style = CALLOUTS[block.variant] ?? CALLOUTS.key_idea;
  const Icon = style.icon;
  return (
    <aside className={clsx("rounded-r-xl border-l-4 px-5 py-4", style.tone)}>
      <div className="mb-1.5 flex items-center gap-2 font-sans text-sm font-semibold text-ink">
        <Icon className="size-4 shrink-0" aria-hidden />
        <span>{block.title || style.label}</span>
      </div>
      <Markdown>{block.markdown}</Markdown>
    </aside>
  );
}
