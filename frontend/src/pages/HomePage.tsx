import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, BookOpenText, Trash2 } from "lucide-react";
import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router";
import { api } from "../api/client";
import { useCourseMutation, useCourses } from "../api/hooks";
import type { CourseListItem } from "../api/types";
import { Badge, Button, Card, ErrorNotice, IconButton, Spinner } from "../components/ui";
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
        <h1 className="font-serif text-4xl font-semibold tracking-tight text-ink sm:text-5xl">
          What do you want to learn?
        </h1>
        <p className="mt-4 text-lg text-ink-2">
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
            placeholder="e.g. how the immune system remembers infections"
            className="h-12 w-full min-w-0 rounded-xl sm:flex-1 border border-line-strong bg-surface px-4 text-base text-ink shadow-sm placeholder:text-ink-3 focus:border-accent focus:outline-none"
          />
          <Button type="submit" size="lg" disabled={goal.trim().length < 3}>
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
              className="rounded-full border border-line bg-surface px-3 py-1 text-sm text-ink-2 hover:border-line-strong hover:text-ink"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </section>

      <section className="mt-16" aria-labelledby="your-courses">
        <h2 id="your-courses" className="mb-4 text-sm font-semibold tracking-wide text-ink-3 uppercase">
          Your courses
        </h2>
        {courses.isPending ? (
          <div className="flex justify-center py-12 text-ink-3">
            <Spinner />
          </div>
        ) : courses.isError ? (
          <ErrorNotice title="Couldn't load your courses" message={courses.error.message} />
        ) : courses.data.length === 0 ? (
          <Card className="flex flex-col items-center gap-4 px-6 py-12 text-center">
            <BookOpenText className="size-8 text-ink-3" aria-hidden />
            <div>
              <p className="font-medium text-ink">No courses yet</p>
              <p className="mt-1 text-sm text-ink-2">
                Start one above, or open a ready-made demo course on Bayesian thinking.
              </p>
            </div>
            <Button variant="secondary" onClick={openDemo} loading={demo.isPending}>
              Try the demo course
            </Button>
            {demo.isError && <p className="text-sm text-danger">{demo.error.message}</p>}
          </Card>
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

const STATUS_TEXT: Record<CourseListItem["status"], string> = {
  diagnostic: "Answer a few questions",
  planning: "Designing your course...",
  planning_failed: "Planning failed",
  outline_ready: "Review your outline",
  in_progress: "",
};

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
    <Card className="group relative flex flex-col p-5 transition-shadow hover:shadow-md">
      <Link to={`/courses/${course.id}`} className="absolute inset-0 rounded-2xl" aria-label={course.title} />
      <div className="flex items-start gap-2">
        <h3 className="flex-1 font-serif text-lg leading-snug font-semibold text-ink">
          {course.title}
        </h3>
        <IconButton
          label="Delete course"
          onClick={remove}
          className="relative z-10 opacity-0 group-hover:opacity-100 focus:opacity-100"
        >
          <Trash2 className="size-4" />
        </IconButton>
      </div>
      <p className="mt-1 line-clamp-2 text-sm text-ink-2">{course.goal}</p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        <Badge>{depthLabel(course.depth)}</Badge>
        <Badge>{styleLabel(course.learning_style)}</Badge>
      </div>
      <div className="mt-auto pt-5">
        {course.status === "in_progress" ? (
          <>
            <div className="h-1.5 overflow-hidden rounded-full bg-surface-2">
              <div className="h-full rounded-full bg-accent" style={{ width: `${progress}%` }} />
            </div>
            <p className="mt-2 text-xs text-ink-3">
              {course.sections_completed} of {plural(course.sections_total, "section")} done
            </p>
          </>
        ) : (
          <p className="text-xs font-medium text-accent">{STATUS_TEXT[course.status]}</p>
        )}
      </div>
    </Card>
  );
}
