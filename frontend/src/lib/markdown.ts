/**
 * remark-math only renders display maths when the $$ fences sit on their own lines, but models
 * often write a whole formula as `$$x^2$$` on one line. Put those fences on their own lines.
 * Fenced code blocks are left untouched.
 */
export function normalizeDisplayMath(markdown: string): string {
  let inCode = false;
  return markdown
    .split("\n")
    .map((line) => {
      if (/^\s*(```|~~~)/.test(line)) inCode = !inCode;
      if (inCode) return line;
      const match = /^(\s*)\$\$(?!\$)(.*[^\s$])\$\$\s*$/.exec(line);
      if (!match) return line;
      const [, indent, tex] = match;
      return `${indent}$$\n${indent}${tex.trim()}\n${indent}$$`;
    })
    .join("\n");
}
