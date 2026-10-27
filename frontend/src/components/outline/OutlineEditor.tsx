import { useMutation, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import {
  ArrowRight,
  ChevronDown,
  ChevronUp,
  CircleAlert,
  CircleCheck,
  CircleDashed,
  Plus,
  Trash2,
  Wand2,
} from "lucide-react";
import { type ReactNode, useEffect, useReducer, useState } from "react";
import { useNavigate } from "react-router";
import { api } from "../../api/client";
import { queryKeys, useCourseMutation } from "../../api/hooks";
import type { Course, LearnerProfile, OutlineUpdate } from "../../api/types";
import { plural } from "../../lib/labels";
import {
  type DraftModule,
  draftFromCourse,
  type OutlineAction,
  outlineProblems,
  outlineReducer,
  savedKeys,
  sectionCount,
  toOutlineUpdate,
} from "../../lib/outline";
import { AutoTextArea, Button, Card, ErrorNotice, IconButton } from "../ui";

const SAVE_DELAY_MS = 800;

// Text that's edited in place: it reads as text until it's hovered or focused
const INLINE_FIELD =
  "block w-full rounded-lg bg-transparent transition-colors focus:bg-surface focus-visible:outline-offset-0";

export function OutlineEditor({ course }: { course: Course }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [draft, dispatch] = useReducer(outlineReducer, course, draftFromCourse);
  // Every edit bumps the version; the outline is saved once nothing has changed for a moment
  const [version, setVersion] = useState(0);
  const [savedVersion, setSavedVersion] = useState(0);
  const [instructions, setInstructions] = useState("");
  const problems = outlineProblems(draft);
  const unsaved = version !== savedVersion;

  const save = useMutation({
    mutationFn: (update: OutlineUpdate) => api.updateOutline(course.id, update),
    onSuccess: (updated) => queryClient.setQueryData(queryKeys.course(updated.id), updated),
  });
  const start = useCourseMutation(() => api.startCourse(course.id));
  const revise = useCourseMutation((text: string) => api.reviseOutline(course.id, text));

  function edit(action: OutlineAction) {
    dispatch(action);
    setVersion((v) => v + 1);
  }

  async function persist(): Promise<boolean> {
    const keys = savedKeys(draft);
    const sending = version;
    try {
      const updated = await save.mutateAsync(toOutlineUpdate(draft));
      dispatch({ type: "assignIds", keys, outline: updated.outline });
      setSavedVersion(sending);
      return true;
    } catch {
      return false;
    }
  }

  useEffect(() => {
    if (!unsaved || problems.length > 0) return;
    const timer = setTimeout(() => void persist(), SAVE_DELAY_MS);
    return () => clearTimeout(timer);
    // persist reads the latest draft, which always changes together with version
  }, [version, unsaved, problems.length]);

  async function startLearning() {
    if (unsaved && !(await persist())) return;
    start.mutate(undefined, {
      onSuccess: (updated) => navigate(`/courses/${updated.id}/learn/${updated.current_section_id}`),
    });
  }

  async function requestRevision() {
    if (unsaved && !(await persist())) return;
    revise.mutate(instructions.trim());
  }

  return (
    <main className="mx-auto max-w-6xl px-4 pt-8 pb-36 sm:px-6 sm:pt-12">
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0">
          <p className="text-sm font-medium text-ink-subtle">Your course outline</p>
          {/* A wrapping field, so long titles break onto balanced lines instead of being cut off */}
          <h1 className="mt-1">
            <AutoTextArea
              singleLine
              value={draft.title}
              onChange={(e) => edit({ type: "setCourse", field: "title", value: e.target.value })}
              aria-label="Course title"
              className={clsx(
                INLINE_FIELD,
                "-mx-2 w-[calc(100%+1rem)] px-2 py-1 font-serif text-3xl leading-tight font-semibold tracking-tighter text-balance text-ink hover:bg-surface-hover sm:text-4xl",
              )}
            />
          </h1>
          <AutoTextArea
            value={draft.description}
            onChange={(e) => edit({ type: "setCourse", field: "description", value: e.target.value })}
            aria-label="Course description"
            placeholder="Describe the course (optional)"
            className={clsx(
              INLINE_FIELD,
              "-mx-2 mt-2 w-[calc(100%+1rem)] px-2 py-1 text-base text-pretty text-ink-muted placeholder:text-ink-subtle hover:bg-surface-hover",
            )}
          />
          <p className="mt-3 text-sm text-pretty text-ink-subtle">
            Edit anything before you start. Nothing has been written yet: each section is written
            when you reach it.
          </p>
          {course.error && (
            <div className="mt-4">
              <ErrorNotice title="Revision failed" message={course.error} />
            </div>
          )}

          <ol className="mt-8 space-y-4">
            {draft.modules.map((module, index) => (
              <ModuleEditor
                key={module.key}
                module={module}
                index={index}
                isFirst={index === 0}
                isLast={index === draft.modules.length - 1}
                canRemove={draft.modules.length > 1}
                edit={edit}
              />
            ))}
          </ol>
          <Button variant="secondary" className="mt-4" onClick={() => edit({ type: "addModule" })}>
            <Plus className="size-4" aria-hidden />
            Add module
          </Button>
        </div>

        <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
          {course.profile && <ProfileCard profile={course.profile} />}
          <Card className="p-5">
            <h2 className="text-base font-semibold text-ink">Want a different shape?</h2>
            <p className="mt-1 text-sm text-ink-muted">
              Describe the changes and Marginalia will rework the outline.
            </p>
            <AutoTextArea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder="More hands-on, and skip the history…"
              aria-label="Changes to make"
              className="mt-3 min-h-20 w-full rounded-lg border border-line-control bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-subtle"
            />
            <Button
              variant="secondary"
              className="mt-3 w-full"
              onClick={requestRevision}
              disabled={!instructions.trim()}
              loading={revise.isPending}
            >
              <Wand2 className="size-4" aria-hidden />
              Revise outline
            </Button>
            {revise.isError && (
              <p className="mt-2 flex gap-2 text-sm text-negative-ink">
                <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
                {revise.error.message}
              </p>
            )}
          </Card>
        </aside>
      </div>

      <footer className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-surface">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3 sm:px-6">
          <div className="min-w-0 flex-1 text-sm">
            {problems.length > 0 ? (
              <Problem>{problems[0]}</Problem>
            ) : save.isError ? (
              <Problem>Couldn't save: {save.error.message}</Problem>
            ) : (
              <p className="truncate text-ink-subtle" role="status">
                {save.isPending ? "Saving…" : unsaved ? "Unsaved changes" : "All changes saved"}
                <span className="hidden sm:inline">
                  {" "}
                  · {plural(sectionCount(draft), "section")}, written just in time
                </span>
              </p>
            )}
            {start.isError && <Problem>{start.error.message}</Problem>}
          </div>
          <Button
            size="lg"
            onClick={startLearning}
            loading={start.isPending}
            disabled={problems.length > 0}
          >
            Start learning
            <ArrowRight className="size-4" aria-hidden />
          </Button>
        </div>
      </footer>
    </main>
  );
}

function Problem({ children }: { children: ReactNode }) {
  return (
    <p className="flex items-center gap-2 text-negative-ink">
      <CircleAlert className="size-4 shrink-0" aria-hidden />
      <span className="truncate">{children}</span>
    </p>
  );
}

function ModuleEditor({
  module,
  index,
  isFirst,
  isLast,
  canRemove,
  edit,
}: {
  module: DraftModule;
  index: number;
  isFirst: boolean;
  isLast: boolean;
  canRemove: boolean;
  edit: (action: OutlineAction) => void;
}) {
  return (
    <li className="rounded-xl border border-line bg-surface p-4 shadow-(--elevation-xs) sm:p-5">
      {/* On phones the actions share the number's row, so the title gets the full width */}
      <div className="flex flex-wrap items-start gap-x-3 gap-y-1 sm:flex-nowrap">
        <span className="mt-1 flex size-7 shrink-0 items-center justify-center rounded-full bg-sunken text-sm font-semibold text-ink-muted tabular-nums">
          {index + 1}
        </span>
        <div className="order-last -mx-1.5 min-w-0 basis-full sm:order-none sm:mx-0 sm:flex-1 sm:basis-auto">
          <AutoTextArea
            singleLine
            value={module.title}
            onChange={(e) =>
              edit({ type: "updateModule", module: module.key, changes: { title: e.target.value } })
            }
            aria-label={`Module ${index + 1} title`}
            placeholder="Module title"
            className={clsx(
              INLINE_FIELD,
              "px-1.5 py-0.5 text-lg font-semibold text-balance text-ink placeholder:text-ink-subtle hover:bg-surface-hover",
            )}
          />
          <AutoTextArea
            value={module.summary}
            onChange={(e) =>
              edit({ type: "updateModule", module: module.key, changes: { summary: e.target.value } })
            }
            aria-label={`Module ${index + 1} summary`}
            placeholder="What this module covers (optional)"
            className={clsx(
              INLINE_FIELD,
              "mt-0.5 px-1.5 py-0.5 text-sm text-pretty text-ink-muted placeholder:text-ink-subtle hover:bg-surface-hover",
            )}
          />
        </div>
        <div className="ml-auto flex sm:ml-0">
          <IconButton
            label="Move module up"
            disabled={isFirst}
            onClick={() => edit({ type: "moveModule", module: module.key, by: -1 })}
          >
            <ChevronUp className="size-4" />
          </IconButton>
          <IconButton
            label="Move module down"
            disabled={isLast}
            onClick={() => edit({ type: "moveModule", module: module.key, by: 1 })}
          >
            <ChevronDown className="size-4" />
          </IconButton>
          <IconButton
            label="Delete module"
            disabled={!canRemove}
            onClick={() => edit({ type: "removeModule", module: module.key })}
          >
            <Trash2 className="size-4" />
          </IconButton>
        </div>
      </div>

      <ol className="mt-3 space-y-1 sm:pl-10">
        {module.sections.map((section, sectionIndex) => (
          <li
            key={section.key}
            className="group flex flex-wrap items-start gap-x-2 rounded-lg p-1 transition-colors hover:bg-surface-hover sm:flex-nowrap"
          >
            <span className="mt-1.5 w-8 shrink-0 text-xs font-medium text-ink-subtle tabular-nums">
              {index + 1}.{sectionIndex + 1}
            </span>
            <div className="min-w-0 flex-1">
              <AutoTextArea
                singleLine
                value={section.title}
                onChange={(e) =>
                  edit({
                    type: "updateSection",
                    module: module.key,
                    section: section.key,
                    changes: { title: e.target.value },
                  })
                }
                aria-label={`Section ${index + 1}.${sectionIndex + 1} title`}
                placeholder="Section title"
                className={clsx(
                  INLINE_FIELD,
                  "px-1.5 py-0.5 text-base font-medium text-balance text-ink placeholder:text-ink-subtle",
                )}
              />
              <AutoTextArea
                value={section.summary}
                onChange={(e) =>
                  edit({
                    type: "updateSection",
                    module: module.key,
                    section: section.key,
                    changes: { summary: e.target.value },
                  })
                }
                aria-label={`Section ${index + 1}.${sectionIndex + 1} summary`}
                placeholder="What it teaches (optional)"
                className={clsx(
                  INLINE_FIELD,
                  "px-1.5 py-0.5 text-sm text-pretty text-ink-muted placeholder:text-ink-subtle",
                )}
              />
            </div>
            {/* Revealed on hover with a mouse; always there on touch screens */}
            <div className="flex w-full justify-end sm:w-auto pointer-fine:opacity-0 pointer-fine:group-focus-within:opacity-100 pointer-fine:group-hover:opacity-100">
              <IconButton
                label="Move section up"
                disabled={isFirst && sectionIndex === 0}
                onClick={() =>
                  edit({ type: "moveSection", module: module.key, section: section.key, by: -1 })
                }
              >
                <ChevronUp className="size-4" />
              </IconButton>
              <IconButton
                label="Move section down"
                disabled={isLast && sectionIndex === module.sections.length - 1}
                onClick={() =>
                  edit({ type: "moveSection", module: module.key, section: section.key, by: 1 })
                }
              >
                <ChevronDown className="size-4" />
              </IconButton>
              <IconButton
                label="Delete section"
                onClick={() =>
                  edit({ type: "removeSection", module: module.key, section: section.key })
                }
              >
                <Trash2 className="size-4" />
              </IconButton>
            </div>
          </li>
        ))}
        {module.sections.length === 0 && (
          <li className="flex items-center gap-2 px-2 py-1 text-sm text-negative-ink">
            <CircleAlert className="size-4 shrink-0" aria-hidden />
            Add at least one section.
          </li>
        )}
      </ol>
      <Button
        variant="ghost"
        size="sm"
        className="mt-2 -ml-1 sm:ml-9"
        onClick={() => edit({ type: "addSection", module: module.key })}
      >
        <Plus className="size-4" aria-hidden />
        Add section
      </Button>
    </li>
  );
}

function ProfileCard({ profile }: { profile: LearnerProfile }) {
  return (
    <Card className="p-5">
      <h2 className="text-sm font-medium text-ink-subtle">Where you're starting</h2>
      <p className="mt-1 text-lg font-semibold text-ink capitalize">{profile.level}</p>
      <p className="mt-2 text-sm text-pretty text-ink-muted">{profile.summary}</p>
      <ProfileList title="You already know" items={profile.strengths} icon={CircleCheck} tone="text-positive" />
      <ProfileList title="Still to learn" items={profile.gaps} icon={CircleDashed} tone="text-ink-subtle" />
    </Card>
  );
}

// Strengths and gaps are phrases, often long ones, so they're a wrapping list rather than pills
function ProfileList({
  title,
  items,
  icon: Icon,
  tone,
}: {
  title: string;
  items: string[];
  icon: typeof CircleCheck;
  tone: string;
}) {
  if (items.length === 0) return null;
  return (
    <div className="mt-4 border-t border-line pt-4">
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      <ul className="mt-2 space-y-2">
        {items.map((item) => (
          <li key={item} className="flex gap-2 text-sm text-ink-muted">
            <Icon className={clsx("mt-0.5 size-4 shrink-0", tone)} aria-hidden />
            <span className="min-w-0">{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
