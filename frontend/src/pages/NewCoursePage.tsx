import clsx from "clsx";
import { BookOpen, Eye, Hammer, Lightbulb } from "lucide-react";
import { type FormEvent, type ReactNode, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { api } from "../api/client";
import { useCourseMutation } from "../api/hooks";
import type { CourseCreate, Depth, LearningStyle } from "../api/types";
import { AutoTextArea, Button, ErrorNotice } from "../components/ui";
import { DEPTHS, STYLES } from "../lib/labels";

const STYLE_ICONS: Record<LearningStyle, typeof Eye> = {
  visual: Eye,
  reading: BookOpen,
  hands_on: Hammer,
  intuition: Lightbulb,
};

const FIELD =
  "min-h-12 w-full rounded-lg border border-line-control bg-surface px-4 py-3 text-base text-ink shadow-(--elevation-xs) placeholder:text-ink-subtle";

export function NewCoursePage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [goal, setGoal] = useState(params.get("goal") ?? "");
  const [depth, setDepth] = useState<Depth>("practitioner");
  const [style, setStyle] = useState<LearningStyle>("visual");
  const [background, setBackground] = useState("");
  const create = useCourseMutation((data: CourseCreate) => api.createCourse(data));

  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate(
      { goal: goal.trim(), depth, learning_style: style, background: background.trim() },
      { onSuccess: (course) => navigate(`/courses/${course.id}`) },
    );
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-10 sm:px-6 sm:py-14">
      <h1 className="font-serif text-3xl font-semibold tracking-tighter text-ink sm:text-4xl">
        New course
      </h1>
      <p className="mt-2 text-base text-pretty text-ink-muted">
        Tell Marginalia what you're after. You'll answer a few quick questions next, then review
        the outline before anything is written.
      </p>

      <form onSubmit={submit} className="mt-10 space-y-10">
        <Step number={1} title="What do you want to learn?" fieldId="goal">
          <AutoTextArea
            id="goal"
            value={goal}
            onChange={(event) => setGoal(event.target.value)}
            placeholder="How memory cells fight infection…"
            maxLength={500}
            required
            autoFocus={!goal}
            className={FIELD}
          />
        </Step>

        <Step number={2} title="How deep do you want to go?">
          <div className="grid gap-3 sm:grid-cols-3">
            {DEPTHS.map((option) => (
              <Choice
                key={option.value}
                name="depth"
                checked={depth === option.value}
                onChange={() => setDepth(option.value)}
                label={option.label}
                description={option.description}
              />
            ))}
          </div>
        </Step>

        <Step number={3} title="How do you like to learn?">
          <div className="grid gap-3 sm:grid-cols-2">
            {STYLES.map((option) => {
              const Icon = STYLE_ICONS[option.value];
              return (
                <Choice
                  key={option.value}
                  name="style"
                  checked={style === option.value}
                  onChange={() => setStyle(option.value)}
                  label={option.label}
                  description={option.description}
                  icon={<Icon className="size-5" aria-hidden />}
                />
              );
            })}
          </div>
        </Step>

        <Step number={4} title="Anything you already know?" optional fieldId="background">
          <AutoTextArea
            id="background"
            value={background}
            onChange={(event) => setBackground(event.target.value)}
            placeholder="I studied chemistry at school but never biology…"
            maxLength={1000}
            className={FIELD}
          />
        </Step>

        <div className="space-y-4">
          {create.isError && (
            <ErrorNotice title="Couldn't start the course" message={create.error.message} />
          )}
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-end">
            {create.isPending && (
              <span role="status" className="text-sm text-ink-subtle">
                Writing a few quick questions…
              </span>
            )}
            <Button type="submit" size="lg" loading={create.isPending} disabled={goal.trim().length < 3}>
              Continue
            </Button>
          </div>
        </div>
      </form>
    </main>
  );
}

/** One step of the form: a labelled field, or a group of choices when there's no `fieldId`. */
function Step({
  number,
  title,
  optional = false,
  fieldId,
  children,
}: {
  number: number;
  title: string;
  optional?: boolean;
  fieldId?: string;
  children: ReactNode;
}) {
  const heading = (
    <>
      <span
        aria-hidden
        className="flex size-6 shrink-0 items-center justify-center rounded-full border border-line-strong text-xs font-semibold text-ink-muted tabular-nums"
      >
        {number}
      </span>
      <span className="text-base font-semibold text-ink">{title}</span>
      {optional && <span className="text-sm text-ink-subtle">Optional</span>}
    </>
  );
  const headingClass = "mb-3 flex items-center gap-3";
  if (fieldId) {
    return (
      <div>
        <label htmlFor={fieldId} className={headingClass}>
          {heading}
        </label>
        {children}
      </div>
    );
  }
  return (
    <fieldset>
      <legend className={headingClass}>{heading}</legend>
      {children}
    </fieldset>
  );
}

function Choice({
  name,
  checked,
  onChange,
  label,
  description,
  icon,
}: {
  name: string;
  checked: boolean;
  onChange: () => void;
  label: string;
  description: string;
  icon?: ReactNode;
}) {
  return (
    <label
      className={clsx(
        "flex cursor-pointer gap-3 rounded-xl border p-4 transition-colors",
        "has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-brand",
        checked
          ? "border-brand bg-brand-soft ring-1 ring-brand"
          : "border-line bg-surface hover:border-line-strong",
      )}
    >
      <input type="radio" name={name} checked={checked} onChange={onChange} className="sr-only" />
      {icon && <span className={clsx("mt-0.5", checked ? "text-brand-ink" : "text-ink-subtle")}>{icon}</span>}
      <span className="min-w-0 flex-1">
        <span className="block text-base font-medium text-ink">{label}</span>
        <span className="mt-1 block text-sm text-ink-muted">{description}</span>
      </span>
      {/* The radio's state, drawn so selection shows by more than colour */}
      <span
        aria-hidden
        className={clsx(
          "mt-1 flex size-4 shrink-0 items-center justify-center rounded-full border",
          checked ? "border-brand bg-brand" : "border-line-control bg-surface",
        )}
      >
        {checked && <span className="size-1.5 rounded-full bg-on-brand" />}
      </span>
    </label>
  );
}
