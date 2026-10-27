import clsx from "clsx";
import { Check } from "lucide-react";
import { useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router";
import { ApiError, api } from "../api/client";
import { useCourse, useCourseMutation } from "../api/hooks";
import type { Course, DiagnosticAnswer } from "../api/types";
import { OutlineEditor } from "../components/outline/OutlineEditor";
import { Button, Card, ErrorNotice, Spinner } from "../components/ui";

export function CoursePage() {
  const { courseId = "" } = useParams();
  const course = useCourse(courseId);

  if (course.isPending) return <PageSpinner />;
  if (course.isError) {
    const missing = course.error instanceof ApiError && course.error.status === 404;
    return (
      <main className="mx-auto max-w-2xl px-4 py-16">
        <ErrorNotice
          title={missing ? "Course not found" : "Couldn't load this course"}
          message={missing ? "It may have been deleted." : course.error.message}
        />
      </main>
    );
  }

  const data = course.data;
  switch (data.status) {
    case "diagnostic":
      return <DiagnosticView course={data} />;
    case "planning":
      return <PlanningView course={data} />;
    case "planning_failed":
      return <PlanningFailed course={data} />;
    case "outline_ready":
      return <OutlineEditor course={data} />;
    case "in_progress": {
      const sectionId = data.current_section_id ?? data.sections[0]?.id;
      return <Navigate to={`/courses/${data.id}/learn/${sectionId}`} replace />;
    }
  }
}

export function PageSpinner() {
  return (
    <div className="flex justify-center py-24 text-ink-subtle">
      <Spinner className="size-6" />
    </div>
  );
}

type Choice = number | "unsure";

function DiagnosticView({ course }: { course: Course }) {
  const [choices, setChoices] = useState<Record<string, Choice>>({});
  const submit = useCourseMutation((answers: DiagnosticAnswer[]) =>
    api.submitAnswers(course.id, answers),
  );
  const answered = course.diagnostics.filter((q) => choices[q.id] !== undefined).length;
  const complete = answered === course.diagnostics.length;

  function send(skip = false) {
    const answers = skip
      ? []
      : course.diagnostics.map((q) => ({
          question_id: q.id,
          option: choices[q.id] === "unsure" ? null : (choices[q.id] as number),
        }));
    submit.mutate(answers);
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-10 sm:px-6 sm:py-14">
      <p className="text-sm font-medium text-brand-ink">{course.title}</p>
      <h1 className="mt-1 font-serif text-3xl font-semibold tracking-tight">A few quick questions</h1>
      <p className="mt-2 text-ink-muted">
        These help the course start where you are. Pick "I'm not sure" whenever you are: a guess
        tells us less than an honest "not sure".
      </p>

      <div className="mt-8 space-y-4">
        {course.diagnostics.map((question, index) => (
          <Card key={question.id} className="p-5 sm:p-6">
            <fieldset>
              <legend className="font-medium text-ink">
                <span className="mr-2 text-ink-subtle">{index + 1}.</span>
                {question.question}
              </legend>
              <div className="mt-4 space-y-2">
                {[...question.options.map((option, i) => [i, option] as const), ["unsure", "I'm not sure"] as const].map(
                  ([value, label]) => {
                    const selected = choices[question.id] === value;
                    return (
                      <label
                        key={String(value)}
                        className={clsx(
                          "flex cursor-pointer items-center gap-3 rounded-lg border px-4 py-2.5 text-sm transition-colors",
                          selected
                            ? "border-brand bg-brand-soft/60 text-ink"
                            : "border-line text-ink-muted hover:border-line-strong hover:text-ink",
                          value === "unsure" && !selected && "border-dashed",
                        )}
                      >
                        <input
                          type="radio"
                          name={question.id}
                          checked={selected}
                          onChange={() => setChoices((c) => ({ ...c, [question.id]: value }))}
                          className="size-4 accent-[var(--brand)]"
                        />
                        {label}
                      </label>
                    );
                  },
                )}
              </div>
            </fieldset>
          </Card>
        ))}
      </div>

      {submit.isError && (
        <div className="mt-6">
          <ErrorNotice message={submit.error.message} />
        </div>
      )}
      <div className="mt-8 flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Button variant="ghost" onClick={() => send(true)} disabled={submit.isPending}>
          Skip the questions
        </Button>
        <Button size="lg" onClick={() => send()} disabled={!complete} loading={submit.isPending}>
          {complete ? "Plan my course" : `Answer all ${course.diagnostics.length} to continue`}
        </Button>
      </div>
    </main>
  );
}

const PLANNING_STEPS = ["Reading your answers", "Sketching where you're starting from", "Planning modules and sections"];
const REVISING_STEPS = ["Reading your instructions", "Reworking the outline"];

function PlanningView({ course }: { course: Course }) {
  const revising = course.outline.length > 0;
  const steps = revising ? REVISING_STEPS : PLANNING_STEPS;
  return (
    <main className="mx-auto flex max-w-lg flex-col items-center px-4 py-24 text-center">
      <Spinner className="size-8 text-brand-ink" />
      <h1 className="mt-6 font-serif text-2xl font-semibold">
        {revising ? "Revising your outline" : "Designing your course"}
      </h1>
      <p className="mt-2 text-ink-muted">{course.goal}</p>
      <ul className="mt-8 space-y-2 text-left text-sm text-ink-muted">
        {steps.map((step) => (
          <li key={step} className="flex items-center gap-2">
            <Check className="size-4 text-ink-subtle" aria-hidden />
            {step}
          </li>
        ))}
      </ul>
      <p className="mt-8 text-xs text-ink-subtle">This usually takes under a minute.</p>
    </main>
  );
}

function PlanningFailed({ course }: { course: Course }) {
  const navigate = useNavigate();
  const retry = useCourseMutation(() => api.retryPlanning(course.id));
  return (
    <main className="mx-auto max-w-2xl px-4 py-16">
      <ErrorNotice
        title="The course couldn't be planned"
        message={course.error ?? "Something went wrong."}
        action={
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={() => navigate("/")}>
              Back
            </Button>
            <Button size="sm" onClick={() => retry.mutate(undefined)} loading={retry.isPending}>
              Try again
            </Button>
          </div>
        }
      />
    </main>
  );
}
