import { Check, Copy } from "lucide-react";
import { useMemo, useState } from "react";
import { highlightCode } from "./highlight";

export function CodeBlock({
  language,
  code,
  caption,
}: {
  language: string;
  code: string;
  caption?: string;
}) {
  const html = useMemo(() => highlightCode(code, language), [code, language]);
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard access needs a secure context; nothing to do without it
    }
  }

  return (
    <figure className="overflow-hidden rounded-xl border border-line bg-[var(--code-bg)]">
      <div
        className="flex items-center justify-between border-b border-line px-4 py-1.5 font-sans text-xs text-ink-subtle"
        data-anchor-ignore
      >
        <span>{language || "code"}</span>
        <button
          type="button"
          onClick={copy}
          className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 hover:bg-surface-hover hover:text-ink"
        >
          {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="overflow-x-auto px-4 py-3 font-mono text-[0.84rem] leading-relaxed">
        <code className="hljs" dangerouslySetInnerHTML={{ __html: html }} />
      </pre>
      {caption ? (
        <figcaption className="border-t border-line px-4 py-2 font-sans text-sm text-ink-muted">
          {caption}
        </figcaption>
      ) : null}
    </figure>
  );
}
