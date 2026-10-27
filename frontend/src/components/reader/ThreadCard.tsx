import clsx from "clsx";
import { Check, RotateCcw, SendHorizontal, Sparkles, Trash2 } from "lucide-react";
import { type FormEvent, type KeyboardEvent, useState } from "react";
import { useCreateThread, useDeleteThread, useReply, useResolveThread } from "../../api/hooks";
import type { Thread } from "../../api/types";
import type { Anchor } from "./hooks";
import { Markdown } from "../markdown/Markdown";
import { AutoTextArea, Button, IconButton, TypingDots } from "../ui";

const QUICK_QUESTIONS = ["Explain this more simply", "Give me an example", "Why is this true?"];

function TutorMark() {
  return (
    <span
      className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-accent-soft text-accent"
      aria-label="Tutor"
    >
      <Sparkles className="size-3.5" aria-hidden />
    </span>
  );
}

function Quote({ text }: { text: string }) {
  return (
    <blockquote className="line-clamp-3 border-l-2 border-mark-solid pl-2.5 font-serif text-sm text-ink-2 italic">
      {text}
    </blockquote>
  );
}

/** Enter sends; Shift+Enter starts a new line. */
function submitOnEnter(submit: () => void) {
  return (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  };
}

export function ThreadCard({
  thread,
  sectionId,
  active,
  onActivate,
}: {
  thread: Thread;
  sectionId: string;
  active: boolean;
  onActivate: () => void;
}) {
  const reply = useReply(sectionId);
  const resolve = useResolveThread(sectionId);
  const remove = useDeleteThread(sectionId);
  const [text, setText] = useState("");

  function send() {
    const content = text.trim();
    if (!content || reply.isPending) return;
    reply.mutate({ threadId: thread.id, content }, { onSuccess: () => setText("") });
  }

  return (
    <div
      onClick={onActivate}
      className={clsx(
        "rounded-xl border bg-surface p-3.5 shadow-sm transition-[border-color,box-shadow]",
        active ? "border-accent/50 shadow-md ring-2 ring-accent/15" : "border-line hover:border-line-strong",
      )}
    >
      <div className="flex items-start gap-1">
        <div className="min-w-0 flex-1">
          <Quote text={thread.quote} />
        </div>
        <IconButton
          label={thread.resolved ? "Reopen" : "Resolve"}
          onClick={(event) => {
            event.stopPropagation();
            resolve.mutate({ threadId: thread.id, resolved: !thread.resolved });
          }}
        >
          {thread.resolved ? <RotateCcw className="size-4" /> : <Check className="size-4" />}
        </IconButton>
        <IconButton
          label="Delete"
          onClick={(event) => {
            event.stopPropagation();
            if (window.confirm("Delete this thread?")) remove.mutate(thread.id);
          }}
        >
          <Trash2 className="size-4" />
        </IconButton>
      </div>

      {thread.resolved && !active ? (
        <p className="mt-2 text-xs text-ink-3">Resolved · {thread.messages[0]?.content}</p>
      ) : (
        <div className="mt-3 space-y-3">
          {thread.messages.map((message) =>
            message.role === "learner" ? (
              <p key={message.id} className="text-sm font-medium text-ink">
                {message.content}
              </p>
            ) : (
              <div key={message.id} className="flex gap-2.5">
                <TutorMark />
                <Markdown compact className="min-w-0 flex-1 text-ink">
                  {message.content}
                </Markdown>
              </div>
            ),
          )}
          {reply.isPending && (
            <>
              <p className="text-sm font-medium text-ink">{reply.variables.content}</p>
              <div className="flex items-center gap-2.5">
                <TutorMark />
                <TypingDots label="The tutor is thinking" />
              </div>
            </>
          )}
        </div>
      )}

      {reply.isError && <p className="mt-2 text-xs text-danger">{reply.error.message}</p>}
      {active && !thread.resolved && (
        <form
          onSubmit={(event: FormEvent) => {
            event.preventDefault();
            send();
          }}
          onClick={(event) => event.stopPropagation()}
          className="mt-3 flex items-end gap-1.5 border-t border-line pt-3"
        >
          <AutoTextArea
            value={text}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={submitOnEnter(send)}
            placeholder="Ask a follow-up..."
            aria-label="Follow-up question"
            className="max-h-40 min-w-0 flex-1 rounded-lg border border-line bg-surface-2/50 px-3 py-2 text-sm text-ink placeholder:text-ink-3 focus:border-accent focus:outline-none"
          />
          <IconButton type="submit" label="Send" disabled={!text.trim() || reply.isPending}>
            <SendHorizontal className="size-4" />
          </IconButton>
        </form>
      )}
    </div>
  );
}

export function Composer({
  anchor,
  sectionId,
  onCreated,
  onCancel,
}: {
  anchor: Anchor;
  sectionId: string;
  onCreated: (threadId: string) => void;
  onCancel: () => void;
}) {
  const create = useCreateThread(sectionId);
  const [question, setQuestion] = useState("");

  function ask(text = question) {
    const trimmed = text.trim();
    if (!trimmed || create.isPending) return;
    setQuestion(trimmed);
    create.mutate(
      {
        block_id: anchor.blockId,
        quote: anchor.quote,
        prefix: anchor.prefix,
        suffix: anchor.suffix,
        question: trimmed,
      },
      { onSuccess: (thread) => onCreated(thread.id) },
    );
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        ask();
      }}
      className="rounded-xl border border-accent/50 bg-surface p-3.5 shadow-md ring-2 ring-accent/15"
    >
      <Quote text={anchor.quote} />
      {create.isPending ? (
        <div className="mt-3 space-y-3">
          <p className="text-sm font-medium text-ink">{question}</p>
          <div className="flex items-center gap-2.5">
            <TutorMark />
            <TypingDots label="The tutor is thinking" />
            <span className="text-xs text-ink-3">Reading the passage...</span>
          </div>
        </div>
      ) : (
        <>
          <AutoTextArea
            autoFocus
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={submitOnEnter(() => ask())}
            placeholder="What would you like to know about this?"
            aria-label="Your question"
            className="mt-3 max-h-48 w-full rounded-lg border border-line bg-surface-2/50 px-3 py-2 text-sm text-ink placeholder:text-ink-3 focus:border-accent focus:outline-none"
          />
          <div className="mt-2 flex flex-wrap gap-1.5">
            {QUICK_QUESTIONS.map((quick) => (
              <button
                key={quick}
                type="button"
                onClick={() => ask(quick)}
                className="rounded-full border border-line px-2.5 py-0.5 text-xs text-ink-2 hover:border-accent hover:text-accent"
              >
                {quick}
              </button>
            ))}
          </div>
          {create.isError && <p className="mt-2 text-xs text-danger">{create.error.message}</p>}
          <div className="mt-3 flex justify-end gap-2">
            <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={!question.trim()}>
              Ask
            </Button>
          </div>
        </>
      )}
    </form>
  );
}
