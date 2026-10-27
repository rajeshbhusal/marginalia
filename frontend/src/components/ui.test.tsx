import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { type KeyboardEvent, useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { AutoTextArea } from "./ui";

function Field({
  singleLine = false,
  initial = "",
  onKeyDown,
}: {
  singleLine?: boolean;
  initial?: string;
  onKeyDown?: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
}) {
  const [value, setValue] = useState(initial);
  return (
    <AutoTextArea
      aria-label="Field"
      singleLine={singleLine}
      value={value}
      onChange={(event) => setValue(event.target.value)}
      onKeyDown={onKeyDown}
    />
  );
}

describe("AutoTextArea", () => {
  it("turns pasted line breaks into spaces without moving the caret", async () => {
    const user = userEvent.setup();
    render(<Field singleLine initial="Hello world" />);
    const field = screen.getByRole<HTMLTextAreaElement>("textbox", { name: "Field" });
    await user.click(field);
    field.setSelectionRange(5, 5);
    await user.paste("\nthere\n");
    expect(field).toHaveValue("Hello there world");
    expect(field.selectionStart).toBe("Hello there ".length);
    await user.keyboard("X");
    expect(field).toHaveValue("Hello there Xworld");
  });

  it("ignores Enter on a single line but still passes the key on", async () => {
    const user = userEvent.setup();
    const onKeyDown = vi.fn();
    render(<Field singleLine initial="Title" onKeyDown={onKeyDown} />);
    await user.type(screen.getByRole("textbox", { name: "Field" }), "{Enter}");
    expect(screen.getByRole("textbox", { name: "Field" })).toHaveValue("Title");
    expect(onKeyDown).toHaveBeenCalledWith(expect.objectContaining({ key: "Enter" }));
  });

  it("leaves Enter to the caller otherwise, as the margin composer needs", async () => {
    const user = userEvent.setup();
    const onKeyDown = vi.fn();
    render(<Field initial="Line one" onKeyDown={onKeyDown} />);
    await user.type(screen.getByRole("textbox", { name: "Field" }), "{Enter}Line two");
    expect(screen.getByRole("textbox", { name: "Field" })).toHaveValue("Line one\nLine two");
    expect(onKeyDown).toHaveBeenCalledWith(expect.objectContaining({ key: "Enter" }));
  });
});
