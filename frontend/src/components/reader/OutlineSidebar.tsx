import clsx from "clsx";
import { ArrowLeft, CircleAlert, CircleCheck, Circle, CircleDot, X } from "lucide-react";
import { Link } from "react-router";
import type { Course, SectionSummary } from "../../api/types";
import { IconButton, Spinner } from "../ui";

function StatusIcon({ section }: { section?: SectionSummary }) {
  if (section?.completed_at) return <CircleCheck className="size-4 text-success" aria-label="Completed" />;
  switch (section?.status) {
    case "generating":
      return <Spinner className="size-4 text-accent" />;
    case "failed":
      return <CircleAlert className="size-4 text-danger" aria-label="Failed" />;
    case "ready":
      return <CircleDot className="size-4 text-accent" aria-label="Ready" />;
    default:
      return <Circle className="size-4 text-ink-3" aria-label="Not written yet" />;
  }
}

function Contents({ course, currentSectionId }: { course: Course; currentSectionId: string }) {
  const sections = new Map(course.sections.map((s) => [s.id, s]));
  const completed = course.sections.filter((s) => s.completed_at).length;
  const total = course.sections.length;

  return (
    <nav aria-label="Course contents" className="space-y-6 p-5">
      <div>
        <Link to="/" className="inline-flex items-center gap-1 text-xs text-ink-3 hover:text-ink">
          <ArrowLeft className="size-3.5" aria-hidden />
          All courses
        </Link>
        <p className="mt-2 font-serif text-lg leading-snug font-semibold text-ink">{course.title}</p>
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-surface-2">
          <div
            className="h-full rounded-full bg-accent transition-[width]"
            style={{ width: `${total ? (completed / total) * 100 : 0}%` }}
          />
        </div>
        <p className="mt-1.5 text-xs text-ink-3">
          {completed} of {total} complete
        </p>
      </div>
      {course.outline.map((module, moduleIndex) => (
        <div key={module.id}>
          <p className="text-xs font-semibold tracking-wide text-ink-3 uppercase">
            Module {moduleIndex + 1}
          </p>
          <p className="mt-0.5 text-sm font-semibold text-ink">{module.title}</p>
          <ul className="mt-2 space-y-0.5">
            {module.sections.map((section) => {
              const current = section.id === currentSectionId;
              return (
                <li key={section.id}>
                  <Link
                    to={`/courses/${course.id}/learn/${section.id}`}
                    aria-current={current ? "page" : undefined}
                    className={clsx(
                      "flex items-start gap-2 rounded-lg px-2 py-1.5 text-sm",
                      current
                        ? "bg-accent-soft font-medium text-ink"
                        : "text-ink-2 hover:bg-surface-2 hover:text-ink",
                    )}
                  >
                    <span className="mt-0.5 shrink-0">
                      <StatusIcon section={sections.get(section.id)} />
                    </span>
                    <span>{section.title}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

/** The course contents: a sidebar on wide screens, a drawer otherwise. */
export function OutlineSidebar({
  course,
  currentSectionId,
  open,
  onClose,
}: {
  course: Course;
  currentSectionId: string;
  open: boolean;
  onClose: () => void;
}) {
  return (
    <>
      <aside className="hidden w-68 shrink-0 border-r border-line xl:block">
        <div className="sticky top-14 max-h-[calc(100dvh-3.5rem)] overflow-y-auto">
          <Contents course={course} currentSectionId={currentSectionId} />
        </div>
      </aside>
      {open && (
        <div className="fixed inset-0 z-40 xl:hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-black/30" onClick={onClose} />
          <div className="absolute inset-y-0 left-0 w-80 max-w-[85vw] overflow-y-auto bg-surface shadow-xl">
            <div className="flex justify-end p-2">
              <IconButton label="Close contents" onClick={onClose}>
                <X className="size-4" />
              </IconButton>
            </div>
            <Contents course={course} currentSectionId={currentSectionId} />
          </div>
        </div>
      )}
    </>
  );
}
