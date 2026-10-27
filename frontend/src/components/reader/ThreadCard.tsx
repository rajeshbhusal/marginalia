import clsx from "clsx";
import { Check, CircleAlert, RotateCcw, SendHorizontal, Sparkles, Trash2 } from "lucide-react";
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
      className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-brand-soft text-brand-ink"
      aria-label="Tutor"
    >
      <Sparkles className="size-3.5" aria-hidden />
    </span>
  );
}

function Quote({ text }: { text: string }) {
  return (
    <blockquote className="line-clamp-3 border-l-2 border-mark-solid pl-3 font-serif text-sm text-ink-muted italic">
      {text}
    </blockquote>
  );
}

function ErrorLine({ message }: { message: string }) {
  return (
    <p className="mt-2 flex gap-2 text-sm text-negative-ink">
      <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
      {message}
    </p>
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
        "rounded-xl border bg-surface p-4 transition-[border-color,box-shadow]",
        active
          ? "border-brand/50 shadow-(--elevation-md) ring-2 ring-brand/15"
          : "border-line shadow-(--elevation-xs) hover:border-line-strong",
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
        <p className="mt-2 text-xs text-ink-subtle">Resolved · {thread.messages[0]?.content}</p>
      ) : (
        <div className="mt-3 space-y-3">
          {thread.messages.map((message) =>
            message.role === "learner" ? (
              <p key={message.id} className="text-sm font-medium text-ink">
                {message.content}
              </p>
            ) : (
              <div key={message.id} className="flex gap-3">
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
              <div className="flex items-center gap-3">
                <TutorMark />
                <TypingDots label="The tutor is thinking" />
              </div>
            </>
          )}
        </div>
      )}

      {reply.isError && <ErrorLine message={reply.error.message} />}
      {active && !thread.resolved && (
        <form
          onSubmit={(event: FormEvent) => {
            event.preventDefault();
            send();
          }}
          onClick={(event) => event.stopPropagation()}
          className="mt-3 flex items-end gap-2 border-t border-line pt-3"
        >
          <AutoTextArea
            value={text}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={submitOnEnter(send)}
            placeholder="Ask a follow-up…"
            aria-label="Follow-up question"
            className="max-h-40 min-w-0 flex-1 rounded-lg border border-line-control bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-subtle"
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
      className="rounded-xl border border-brand/50 bg-surface p-4 shadow-(--elevation-md) ring-2 ring-brand/15"
    >
      <Quote text={anchor.quote} />
      {create.isPending ? (
        <div className="mt-3 space-y-3">
          <p className="text-sm font-medium text-ink">{question}</p>
          <div className="flex items-center gap-3">
            <TutorMark />
            <TypingDots label="The tutor is thinking" />
            <span className="text-xs text-ink-subtle">Reading the passage…</span>
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
            className="mt-3 max-h-48 w-full rounded-lg border border-line-control bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-subtle"
          />
          <div className="mt-2 flex flex-wrap gap-1.5">
            {QUICK_QUESTIONS.map((quick) => (
              <button
                key={quick}
                type="button"
                onClick={() => ask(quick)}
                className="inline-flex items-center rounded-full border border-line px-3 py-1 text-xs text-ink-muted transition-colors hover:border-brand hover:text-brand-ink pointer-coarse:min-h-11"
              >
                {quick}
              </button>
            ))}
          </div>
          {create.isError && <ErrorLine message={create.error.message} />}
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
