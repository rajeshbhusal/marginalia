import { useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import {
  ArrowRight,
  BookOpenText,
  CircleAlert,
  ListChecks,
  ListTree,
  type LucideIcon,
  Trash2,
} from "lucide-react";
import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router";
import { api } from "../api/client";
import { useCourseMutation, useCourses } from "../api/hooks";
import type { CourseListItem } from "../api/types";
import { Button, ErrorNotice, IconButton, Skeleton, Spinner } from "../components/ui";
import { depthLabel, plural, styleLabel } from "../lib/labels";

const SUGGESTIONS = [
  "How vaccines train the immune system",
  "Bayesian statistics",
  "How transformers work",
  "Music theory for guitarists",
];

export function HomePage() {
  const navigate = useNavigate();
  const [goal, setGoal] = useState("");
  const courses = useCourses();
  const demo = useCourseMutation(() => api.createDemoCourse());

  function start(event: FormEvent) {
    event.preventDefault();
    navigate(`/new?goal=${encodeURIComponent(goal.trim())}`);
  }

  function openDemo() {
    demo.mutate(undefined, { onSuccess: (course) => navigate(`/courses/${course.id}`) });
  }

  return (
    <main className="mx-auto max-w-5xl px-4 pt-12 pb-20 sm:px-6 sm:pt-20">
      <section className="mx-auto max-w-2xl text-center">
        <h1 className="font-serif text-4xl font-semibold tracking-tighter text-ink sm:text-5xl sm:tracking-display">
          What do you want to learn?
        </h1>
        <p className="mt-4 text-lg text-pretty text-ink-muted">
          Marginalia plans a course around you, writes each section just in time, and answers
          your questions in the margins.
        </p>
        <form onSubmit={start} className="mt-8 flex flex-col gap-3 sm:flex-row">
          <label htmlFor="goal" className="sr-only">
            What do you want to learn?
          </label>
          <input
            id="goal"
            value={goal}
            onChange={(event) => setGoal(event.target.value)}
            placeholder="How memory cells fight infection…"
            className="h-12 w-full min-w-0 rounded-lg border border-line-control bg-surface px-4 text-base text-ink shadow-(--elevation-xs) placeholder:text-ink-subtle sm:flex-1"
          />
          <Button type="submit" size="xl" disabled={goal.trim().length < 3}>
            Start
            <ArrowRight className="size-4" aria-hidden />
          </Button>
        </form>
        <div className="mt-4 flex flex-wrap justify-center gap-2">
          {SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => setGoal(suggestion)}
              className="inline-flex items-center rounded-full border border-line bg-surface px-3 py-1 text-sm text-ink-muted transition-colors hover:border-line-strong hover:text-ink pointer-coarse:min-h-11"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </section>

      <section className="mt-16" aria-labelledby="my-courses">
        <h2 id="my-courses" className="mb-4 text-lg font-semibold text-ink">
          My courses
        </h2>
        {courses.isPending ? (
          <div role="status" aria-label="Loading your courses" className="appear-delayed grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <CourseCardSkeleton key={i} />
            ))}
          </div>
        ) : courses.isError ? (
          <ErrorNotice
            title="Couldn't load your courses"
            message={courses.error.message}
            action={
              <Button variant="secondary" size="sm" onClick={() => void courses.refetch()}>
                Try again
              </Button>
            }
          />
        ) : courses.data.length === 0 ? (
          <div className="flex flex-col items-center gap-4 rounded-xl border border-dashed border-line-strong px-6 py-12 text-center">
            <BookOpenText className="size-10 text-ink-faint" aria-hidden />
            <div>
              <p className="text-base font-semibold text-ink">No courses yet</p>
              <p className="mt-1 text-sm text-ink-muted">
                Start one above, or open a ready-made demo course on Bayesian thinking.
              </p>
            </div>
            <Button variant="secondary" onClick={openDemo} loading={demo.isPending}>
              Try the demo course
            </Button>
            {demo.isError && <p className="text-sm text-negative-ink">{demo.error.message}</p>}
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {courses.data.map((course) => (
              <CourseCard key={course.id} course={course} />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

/** Whether two strings say the same thing, ignoring case and punctuation. */
function sameText(a: string, b: string): boolean {
  const normalise = (text: string) => text.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, "");
  return normalise(a) === normalise(b);
}

function CourseCard({ course }: { course: CourseListItem }) {
  const queryClient = useQueryClient();
  const progress = course.sections_total
    ? Math.round((course.sections_completed / course.sections_total) * 100)
    : 0;

  async function remove() {
    if (!window.confirm(`Delete "${course.title}"? This can't be undone.`)) return;
    await api.deleteCourse(course.id);
    await queryClient.invalidateQueries({ queryKey: ["courses"] });
  }

  return (
    <article className="group relative flex flex-col rounded-xl border border-line bg-surface p-5 shadow-(--elevation-xs) transition-[border-color,box-shadow] hover:border-line-strong hover:shadow-(--elevation-md)">
      <div className="flex items-start gap-2">
        <h3 className="min-w-0 flex-1 font-serif text-lg leading-snug font-semibold text-ink">
          {/* The link covers the whole card */}
          <Link
            to={`/courses/${course.id}`}
            className="after:absolute after:inset-0 after:rounded-xl focus-visible:outline-none focus-visible:after:outline-2 focus-visible:after:outline-offset-2 focus-visible:after:outline-brand"
          >
            {course.title}
          </Link>
        </h3>
        <IconButton
          label="Delete course"
          onClick={remove}
          className="relative z-10 -mt-1 -mr-2 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 pointer-coarse:opacity-100"
        >
          <Trash2 className="size-4" />
        </IconButton>
      </div>
      {!sameText(course.goal, course.title) && (
        <p className="mt-2 line-clamp-2 text-sm text-ink-muted">{course.goal}</p>
      )}
      <p className="mt-2 text-sm text-ink-subtle">
        {depthLabel(course.depth)} · {styleLabel(course.learning_style)}
      </p>
      <div className="mt-auto pt-5">
        {course.status === "in_progress" ? (
          <>
            <div
              role="progressbar"
              aria-label="Course progress"
              aria-valuenow={progress}
              aria-valuemin={0}
              aria-valuemax={100}
              className="h-1.5 overflow-hidden rounded-full bg-sunken"
            >
              <div className="h-full rounded-full bg-brand" style={{ width: `${progress}%` }} />
            </div>
            <p className="mt-2 text-xs text-ink-subtle tabular-nums">
              {course.sections_completed} of {plural(course.sections_total, "section")} done
            </p>
          </>
        ) : (
          <CourseStatus status={course.status} />
        )}
      </div>
    </article>
  );
}

// A course's next step, or what's happening to it; no icon means it's busy (a spinner)
const STATUS: Record<
  Exclude<CourseListItem["status"], "in_progress">,
  { text: string; icon: LucideIcon | null; tone: string }
> = {
  diagnostic: { text: "Answer a few questions", icon: ListChecks, tone: "text-ink-muted" },
  planning: { text: "Designing your course…", icon: null, tone: "text-ink-muted" },
  planning_failed: { text: "Planning failed", icon: CircleAlert, tone: "text-negative-ink" },
  outline_ready: { text: "Review your outline", icon: ListTree, tone: "text-ink-muted" },
};

function CourseStatus({ status }: { status: keyof typeof STATUS }) {
  const { text, icon: Icon, tone } = STATUS[status];
  return (
    <p className={clsx("flex items-center gap-2 text-sm font-medium", tone)}>
      {Icon ? <Icon className="size-4 shrink-0" aria-hidden /> : <Spinner className="size-4 shrink-0" />}
      {text}
    </p>
  );
}

function CourseCardSkeleton() {
  return (
    <div className="rounded-xl border border-line bg-surface p-5">
      <Skeleton className="h-5 w-4/5" />
      <Skeleton className="mt-2 h-5 w-1/2" />
      <Skeleton className="mt-4 h-3.5 w-full" />
      <Skeleton className="mt-2 h-3.5 w-2/3" />
      <Skeleton className="mt-8 h-1.5 w-full rounded-full" />
    </div>
  );
}
