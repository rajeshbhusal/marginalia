import clsx from "clsx";
import { BookOpen, Eye, Hammer, Lightbulb } from "lucide-react";
import { type FormEvent, type ReactNode, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { api } from "../api/client";
import { useCourseMutation } from "../api/hooks";
import type { CourseCreate, Depth, LearningStyle } from "../api/types";
import { AutoTextArea, Button, Card, ErrorNotice } from "../components/ui";
import { DEPTHS, STYLES } from "../lib/labels";

const STYLE_ICONS: Record<LearningStyle, typeof Eye> = {
  visual: Eye,
  reading: BookOpen,
  hands_on: Hammer,
  intuition: Lightbulb,
};

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
      <h1 className="font-serif text-3xl font-semibold tracking-tight sm:text-4xl">New course</h1>
      <p className="mt-2 text-ink-muted">
        Tell Marginalia what you're after. You'll answer a few quick questions next, then review
        the outline before anything is written.
      </p>

      <form onSubmit={submit} className="mt-8 space-y-6">
        <Step number={1} title="What do you want to learn?">
          <AutoTextArea
            value={goal}
            onChange={(event) => setGoal(event.target.value)}
            placeholder="e.g. how the immune system remembers infections"
            maxLength={500}
            required
            autoFocus={!goal}
            className="min-h-12 w-full rounded-xl border border-line-strong bg-surface px-4 py-3 text-base text-ink placeholder:text-ink-subtle focus:border-brand focus:outline-none"
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

        <Step number={4} title="Anything you already know?" optional>
          <AutoTextArea
            value={background}
            onChange={(event) => setBackground(event.target.value)}
            placeholder="e.g. I studied chemistry at school but never biology"
            maxLength={1000}
            className="min-h-12 w-full rounded-xl border border-line-strong bg-surface px-4 py-3 text-base text-ink placeholder:text-ink-subtle focus:border-brand focus:outline-none"
          />
        </Step>

        {create.isError && (
          <ErrorNotice title="Couldn't start the course" message={create.error.message} />
        )}
        <div className="flex items-center justify-end gap-3">
          {create.isPending && (
            <span className="text-sm text-ink-subtle">Writing a few quick questions...</span>
          )}
          <Button type="submit" size="lg" loading={create.isPending} disabled={goal.trim().length < 3}>
            Continue
          </Button>
        </div>
      </form>
    </main>
  );
}

function Step({
  number,
  title,
  optional = false,
  children,
}: {
  number: number;
  title: string;
  optional?: boolean;
  children: ReactNode;
}) {
  return (
    <Card className="p-5 sm:p-6">
      <fieldset>
        <legend className="mb-4 flex items-center gap-3 font-medium text-ink">
          <span className="flex size-7 items-center justify-center rounded-full bg-brand-soft text-sm font-semibold text-brand-ink">
            {number}
          </span>
          {title}
          {optional && <span className="text-sm font-normal text-ink-subtle">Optional</span>}
        </legend>
        {children}
      </fieldset>
    </Card>
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
        checked
          ? "border-brand bg-brand-soft/60 ring-1 ring-brand"
          : "border-line hover:border-line-strong hover:bg-surface-hover",
      )}
    >
      <input type="radio" name={name} checked={checked} onChange={onChange} className="sr-only" />
      {icon && <span className={clsx("mt-0.5", checked ? "text-brand-ink" : "text-ink-subtle")}>{icon}</span>}
      <span>
        <span className="block font-medium text-ink">{label}</span>
        <span className="mt-0.5 block text-sm text-ink-muted">{description}</span>
      </span>
    </label>
  );
}
