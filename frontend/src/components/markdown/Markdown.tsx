import clsx from "clsx";
import { memo } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import { normalizeDisplayMath } from "../../lib/markdown";
import { CodeBlock } from "./CodeBlock";
import { MermaidDiagram } from "./MermaidDiagram";

interface HastNode {
  type: string;
  tagName?: string;
  value?: string;
  properties?: { className?: unknown };
  children?: HastNode[];
}

function textOf(node: HastNode): string {
  return node.type === "text" ? (node.value ?? "") : (node.children ?? []).map(textOf).join("");
}

const components: Components = {
  a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />,
  // Fenced code: mermaid becomes a diagram, everything else a highlighted block
  pre: ({ node, children }) => {
    const code = (node as HastNode | undefined)?.children?.[0];
    if (code?.type !== "element" || code.tagName !== "code") return <pre>{children}</pre>;
    const classes = Array.isArray(code.properties?.className) ? code.properties.className : [];
    const language =
      classes.map(String).find((c) => c.startsWith("language-"))?.slice("language-".length) ?? "";
    const source = textOf(code).replace(/\n$/, "");
    if (language === "mermaid") return <MermaidDiagram code={source} />;
    return <CodeBlock language={language} code={source} />;
  },
};

/** Markdown with tables, maths and code. Raw HTML is never rendered. */
export const Markdown = memo(function Markdown({
  children,
  compact = false,
  className,
}: {
  children: string;
  compact?: boolean;
  className?: string;
}) {
  return (
    <div className={clsx(compact ? "prose-compact" : "prose-lesson", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: "ignore" }]]}
        components={components}
      >
        {normalizeDisplayMath(children)}
      </ReactMarkdown>
    </div>
  );
});
