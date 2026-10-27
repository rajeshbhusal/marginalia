import { useEffect, useId, useState } from "react";
import { useThemeValue } from "../../lib/theme";

type Mermaid = typeof import("mermaid").default;
let mermaidPromise: Promise<Mermaid> | null = null;

// Mermaid is large, so it's only downloaded when the first diagram appears
function loadMermaid(): Promise<Mermaid> {
  mermaidPromise ??= import("mermaid").then((module) => module.default);
  return mermaidPromise;
}

export function MermaidDiagram({ code, caption }: { code: string; caption?: string }) {
  const theme = useThemeValue();
  const baseId = useId().replace(/[^a-zA-Z0-9]/g, "");
  const [result, setResult] = useState<{ svg?: string; error?: string }>({});

  useEffect(() => {
    let cancelled = false;
    const id = `mermaid-${baseId}-${theme}`;
    void loadMermaid().then(async (mermaid) => {
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        theme: theme === "dark" ? "dark" : "neutral",
        fontFamily: "Inter Variable, ui-sans-serif, system-ui, sans-serif",
      });
      try {
        const { svg } = await mermaid.render(id, code.trim());
        if (!cancelled) setResult({ svg });
      } catch (error) {
        // Mermaid can leave its scratch element behind when parsing fails
        document.getElementById(id)?.remove();
        document.getElementById(`d${id}`)?.remove();
        if (!cancelled) setResult({ error: error instanceof Error ? error.message : String(error) });
      }
    });
    return () => {
      cancelled = true;
    };
  }, [baseId, code, theme]);

  return (
    <figure className="rounded-xl border border-line bg-surface p-4">
      {result.svg ? (
        <div
          className="mermaid-diagram flex justify-center overflow-x-auto"
          data-anchor-ignore
          role="img"
          aria-label={caption || "Diagram"}
          dangerouslySetInnerHTML={{ __html: result.svg }}
        />
      ) : result.error ? (
        <div className="space-y-2 font-sans text-sm" data-anchor-ignore>
          <p className="text-ink-2">This diagram couldn't be drawn, so here is its source.</p>
          <pre className="overflow-x-auto rounded-lg bg-surface-2 p-3 font-mono text-xs text-ink-2">
            {code}
          </pre>
        </div>
      ) : (
        <div
          className="flex h-40 items-center justify-center rounded-lg bg-surface-2 font-sans text-sm text-ink-3"
          data-anchor-ignore
        >
          Drawing diagram...
        </div>
      )}
      {caption ? (
        <figcaption className="mt-3 text-center font-sans text-sm text-ink-2">{caption}</figcaption>
      ) : null}
    </figure>
  );
}
