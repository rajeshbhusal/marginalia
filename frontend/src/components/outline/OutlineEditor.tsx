import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  ChevronDown,
  ChevronUp,
  CircleCheck,
  CircleDashed,
  Plus,
  Trash2,
  Wand2,
} from "lucide-react";
import { useEffect, useReducer, useState } from "react";
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
          <p className="text-sm font-medium text-brand-ink">Your course outline</p>
          {/* A wrapping field, so long titles break onto balanced lines instead of being cut off */}
          <h1 className="mt-1">
            <AutoTextArea
              singleLine
              value={draft.title}
              onChange={(e) => edit({ type: "setCourse", field: "title", value: e.target.value })}
              aria-label="Course title"
              className="-mx-2 block w-[calc(100%+1rem)] rounded-lg bg-transparent px-2 py-1 font-serif text-3xl leading-tight font-semibold tracking-tight text-balance text-ink hover:bg-surface-hover focus:bg-surface focus:outline-none sm:text-4xl"
            />
          </h1>
          <AutoTextArea
            value={draft.description}
            onChange={(e) => edit({ type: "setCourse", field: "description", value: e.target.value })}
            aria-label="Course description"
            placeholder="Describe the course (optional)"
            className="-mx-2 mt-1 w-full rounded-lg bg-transparent px-2 py-1 text-ink-muted hover:bg-surface-hover focus:bg-surface focus:outline-none"
          />
          <p className="mt-3 text-sm text-ink-subtle">
            Edit anything before you start. Nothing has been written yet: each section is written
            when you reach it.
          </p>
          {course.error && (
            <div className="mt-4">
              <ErrorNotice title="Revision failed" message={course.error} />
            </div>
          )}

          <ol className="mt-8 space-y-5">
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
          <Button variant="secondary" className="mt-5" onClick={() => edit({ type: "addModule" })}>
            <Plus className="size-4" aria-hidden />
            Add module
          </Button>
        </div>

        <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
          {course.profile && <ProfileCard profile={course.profile} />}
          <Card className="p-5">
            <p className="font-medium text-ink">Want a different shape?</p>
            <p className="mt-1 text-sm text-ink-muted">
              Describe the changes and Marginalia will rework the outline.
            </p>
            <AutoTextArea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder="e.g. More hands-on, and skip the history"
              aria-label="Changes to make"
              className="mt-3 min-h-20 w-full rounded-lg border border-line-strong bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-subtle focus:border-brand focus:outline-none"
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
            {revise.isError && <p className="mt-2 text-sm text-negative-ink">{revise.error.message}</p>}
          </Card>
        </aside>
      </div>

      <footer className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-surface/95 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3 sm:px-6">
          <div className="min-w-0 flex-1 text-sm">
            {problems.length > 0 ? (
              <p className="truncate text-negative-ink">{problems[0]}</p>
            ) : save.isError ? (
              <p className="truncate text-negative-ink">Couldn't save: {save.error.message}</p>
            ) : (
              <p className="truncate text-ink-subtle">
                {save.isPending ? "Saving..." : unsaved ? "Unsaved changes" : "All changes saved"}
                <span className="hidden sm:inline">
                  {" "}
                  · {plural(sectionCount(draft), "section")}, written just in time
                </span>
              </p>
            )}
            {start.isError && <p className="truncate text-negative-ink">{start.error.message}</p>}
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
    <li className="rounded-2xl border border-line bg-surface p-4 shadow-sm sm:p-5">
      <div className="flex items-start gap-3">
        <span className="mt-1 flex size-7 shrink-0 items-center justify-center rounded-full bg-brand-soft text-sm font-semibold text-brand-ink">
          {index + 1}
        </span>
        <div className="min-w-0 flex-1">
          <AutoTextArea
            singleLine
            value={module.title}
            onChange={(e) =>
              edit({ type: "updateModule", module: module.key, changes: { title: e.target.value } })
            }
            aria-label={`Module ${index + 1} title`}
            placeholder="Module title"
            className="block w-full rounded-md bg-transparent px-1.5 py-0.5 text-lg font-semibold text-balance text-ink hover:bg-surface-hover focus:bg-sunken focus:outline-none"
          />
          <AutoTextArea
            value={module.summary}
            onChange={(e) =>
              edit({ type: "updateModule", module: module.key, changes: { summary: e.target.value } })
            }
            aria-label={`Module ${index + 1} summary`}
            placeholder="What this module covers (optional)"
            className="w-full rounded-md bg-transparent px-1.5 py-0.5 text-sm text-ink-muted hover:bg-surface-hover focus:bg-sunken focus:outline-none"
          />
        </div>
        <div className="flex">
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

      <ol className="mt-3 space-y-0.5 sm:pl-10">
        {module.sections.map((section, sectionIndex) => (
          <li
            key={section.key}
            className="group flex items-start gap-2 rounded-lg px-1 py-1 hover:bg-surface-hover"
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
                className="block w-full rounded-md bg-transparent px-1.5 py-0.5 font-medium text-balance text-ink focus:bg-surface focus:outline-none"
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
                className="w-full rounded-md bg-transparent px-1.5 py-0.5 text-sm text-ink-muted focus:bg-surface focus:outline-none"
              />
            </div>
            <div className="flex sm:opacity-0 sm:group-focus-within:opacity-100 sm:group-hover:opacity-100">
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
          <li className="px-2 py-1 text-sm text-negative-ink">Add at least one section.</li>
        )}
      </ol>
      <button
        type="button"
        onClick={() => edit({ type: "addSection", module: module.key })}
        className="mt-2 inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm font-medium text-brand-ink hover:bg-brand-soft sm:ml-10"
      >
        <Plus className="size-4" aria-hidden />
        Add section
      </button>
    </li>
  );
}

function ProfileCard({ profile }: { profile: LearnerProfile }) {
  return (
    <Card className="p-5">
      <p className="text-xs font-semibold tracking-wide text-ink-subtle uppercase">Where you're starting</p>
      <p className="mt-2 font-medium text-ink capitalize">{profile.level}</p>
      <p className="mt-1 text-sm text-ink-muted">{profile.summary}</p>
      <ProfileList title="You already know" items={profile.strengths} icon={CircleCheck} />
      <ProfileList title="Still to learn" items={profile.gaps} icon={CircleDashed} />
    </Card>
  );
}

// Strengths and gaps are phrases, often long ones, so they're a wrapping list rather than pills
function ProfileList({
  title,
  items,
  icon: Icon,
}: {
  title: string;
  items: string[];
  icon: typeof CircleCheck;
}) {
  if (items.length === 0) return null;
  return (
    <div className="mt-4 border-t border-line pt-4">
      <p className="text-sm font-medium text-ink">{title}</p>
      <ul className="mt-2 space-y-1.5">
        {items.map((item) => (
          <li key={item} className="flex gap-2 text-sm text-ink-muted">
            <Icon className="mt-0.5 size-4 shrink-0 text-ink-subtle" aria-hidden />
            <span className="min-w-0">{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
