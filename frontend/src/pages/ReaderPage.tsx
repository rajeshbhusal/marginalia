import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ExternalLink,
  ListTree,
  MessageSquareText,
  RefreshCw,
} from "lucide-react";
import { type MouseEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { ApiError, api } from "../api/client";
import {
  isWriting,
  queryKeys,
  useCourse,
  useSection,
  useSectionMutation,
  useThreads,
} from "../api/hooks";
import type { Course, ResearchNotes, Section } from "../api/types";
import { BlockView } from "../components/blocks/BlockView";
import { Markdown } from "../components/markdown/Markdown";
import {
  type Anchor,
  anchorAtPoint,
  useAnchorRanges,
  useLayoutVersion,
  useMediaQuery,
  usePaintedHighlights,
  useSelectionAnchor,
} from "../components/reader/hooks";
import { AskButton, MarginColumn, type MarginEntry, MarginSheet } from "../components/reader/Margin";
import { OutlineSidebar } from "../components/reader/OutlineSidebar";
import { Composer, ThreadCard } from "../components/reader/ThreadCard";
import { Badge, Button, ErrorNotice, PageSkeleton, Spinner } from "../components/ui";
import { depthLabel, plural, STAGE_LABELS, styleLabel } from "../lib/labels";

const DRAFT_ID = "draft";

export function ReaderPage() {
  const { courseId = "", sectionId = "" } = useParams();
  const queryClient = useQueryClient();
  const course = useCourse(courseId);
  const section = useSection(sectionId);
  const [contentsOpen, setContentsOpen] = useState(false);

  // Opening a section writes it if it hasn't been yet, and prefetches the next one
  useEffect(() => {
    window.scrollTo({ top: 0 });
    setContentsOpen(false);
    api
      .openSection(sectionId)
      .then((opened) => {
        queryClient.setQueryData(queryKeys.section(opened.id), opened);
        void queryClient.invalidateQueries({ queryKey: queryKeys.course(courseId) });
      })
      .catch(() => {
        // The section query shows the error
      });
  }, [courseId, sectionId, queryClient]);

  // Keep the contents sidebar's status icons in step with this section
  const status = section.data?.status;
  useEffect(() => {
    if (status) void queryClient.invalidateQueries({ queryKey: queryKeys.course(courseId) });
  }, [status, courseId, queryClient]);

  if (course.isPending || section.isPending) return <PageSkeleton />;
  if (course.isError || section.isError) {
    const error = (course.error ?? section.error)!;
    const missing = error instanceof ApiError && error.status === 404;
    return (
      <main className="mx-auto max-w-2xl px-4 py-16">
        <ErrorNotice
          title={missing ? "Section not found" : "Couldn't load this section"}
          message={missing ? "It may belong to a deleted course." : error.message}
        />
      </main>
    );
  }

  return (
    <div className="mx-auto flex max-w-[1440px]">
      <OutlineSidebar
        course={course.data}
        currentSectionId={sectionId}
        open={contentsOpen}
        onClose={() => setContentsOpen(false)}
      />
      <div className="min-w-0 flex-1">
        <SectionView
          key={sectionId}
          course={course.data}
          section={section.data}
          onOpenContents={() => setContentsOpen(true)}
        />
      </div>
    </div>
  );
}

function SectionView({
  course,
  section,
  onOpenContents,
}: {
  course: Course;
  section: Section;
  onOpenContents: () => void;
}) {
  const articleRef = useRef<HTMLElement>(null);
  const desktop = useMediaQuery("(min-width: 1024px)");
  const ready = section.status === "ready";
  const threads = useThreads(section.id, ready);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Anchor | null>(null);
  const [showResolved, setShowResolved] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [selection, clearSelection] = useSelectionAnchor(articleRef, ready);
  const layoutVersion = useLayoutVersion(articleRef);

  const allThreads = useMemo(() => threads.data ?? [], [threads.data]);
  const visible = useMemo(
    () => allThreads.filter((t) => showResolved || !t.resolved || t.id === activeId),
    [allThreads, showResolved, activeId],
  );
  const resolvedCount = allThreads.filter((t) => t.resolved).length;

  const anchors = useMemo<Anchor[]>(() => {
    const list: Anchor[] = visible.map((t) => ({
      id: t.id,
      blockId: t.block_id,
      quote: t.quote,
      prefix: t.prefix,
      suffix: t.suffix,
    }));
    if (draft) list.push(draft);
    return list;
  }, [visible, draft]);
  const ranges = useAnchorRanges(articleRef, anchors, `${layoutVersion}:${section.blocks.length}`);
  const highlighted = draft ? DRAFT_ID : activeId;
  usePaintedHighlights(ranges, highlighted);

  function startQuestion() {
    if (!selection) return;
    const { blockId, quote, prefix, suffix } = selection;
    setDraft({ id: DRAFT_ID, blockId, quote, prefix, suffix });
    setActiveId(null);
    clearSelection();
    setSheetOpen(true);
  }

  function onArticleClick(event: MouseEvent) {
    if (document.getSelection()?.isCollapsed === false) return; // Selecting, not clicking
    const id = anchorAtPoint(ranges, event.clientX, event.clientY);
    if (id && id !== DRAFT_ID) {
      setActiveId(id);
      setSheetOpen(true);
    }
  }

  const entries: MarginEntry[] = anchors.map((anchor) =>
    anchor.id === DRAFT_ID
      ? {
          id: DRAFT_ID,
          blockId: anchor.blockId,
          node: (
            <Composer
              anchor={anchor}
              sectionId={section.id}
              onCreated={(threadId) => {
                setDraft(null);
                setActiveId(threadId);
              }}
              onCancel={() => setDraft(null)}
            />
          ),
        }
      : {
          id: anchor.id,
          blockId: anchor.blockId,
          node: (
            <ThreadCard
              thread={visible.find((t) => t.id === anchor.id)!}
              sectionId={section.id}
              active={activeId === anchor.id}
              onActivate={() => setActiveId(anchor.id)}
            />
          ),
        },
  );
  // On phones, list threads in reading order
  const ordered = [...entries].sort(
    (a, b) =>
      (ranges.get(a.id)?.getBoundingClientRect().top ?? 0) -
      (ranges.get(b.id)?.getBoundingClientRect().top ?? 0),
  );

  return (
    <div className="flex gap-10 px-4 py-8 sm:px-8 lg:py-10">
      <article ref={articleRef} onClick={onArticleClick} className="min-w-0 max-w-[44rem] flex-1">
        <SectionHeader course={course} section={section} onOpenContents={onOpenContents} />
        {ready && (
          <MarginSummary
            count={allThreads.length - resolvedCount}
            resolved={resolvedCount}
            showResolved={showResolved}
            onToggleResolved={() => setShowResolved((s) => !s)}
          />
        )}
        <SectionBody section={section} />
        {ready && <SectionFooter course={course} section={section} />}
      </article>

      {desktop && (
        <aside className="w-80 shrink-0" aria-label="Margin notes">
          <MarginColumn
            entries={entries}
            ranges={ranges}
            activeId={draft ? DRAFT_ID : activeId}
            articleRef={articleRef}
            layoutVersion={layoutVersion}
          />
        </aside>
      )}
      {!desktop && (
        <MarginSheet open={sheetOpen && entries.length > 0} onClose={() => setSheetOpen(false)}>
          {ordered.map((entry) => (
            <div key={entry.id}>{entry.node}</div>
          ))}
        </MarginSheet>
      )}
      {!desktop && !selection && entries.length > 0 && !sheetOpen && (
        <button
          type="button"
          onClick={() => setSheetOpen(true)}
          className="fixed right-4 bottom-5 z-30 flex items-center gap-2 rounded-full border border-line bg-surface px-4 py-2.5 text-sm font-medium text-ink shadow-lg"
        >
          <MessageSquareText className="size-4" aria-hidden />
          {plural(entries.length, "note")}
        </button>
      )}
      {selection && !draft && <AskButton anchor={selection} onAsk={startQuestion} docked={!desktop} />}
    </div>
  );
}

function SectionHeader({
  course,
  section,
  onOpenContents,
}: {
  course: Course;
  section: Section;
  onOpenContents: () => void;
}) {
  return (
    <header className="mb-6">
      <button
        type="button"
        onClick={onOpenContents}
        className="mb-4 inline-flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1 text-sm text-ink-muted hover:bg-surface-hover xl:hidden"
      >
        <ListTree className="size-4" aria-hidden />
        Contents
      </button>
      <p className="text-sm font-medium text-brand-ink">
        Module {section.module_index + 1} · {section.module_title}
      </p>
      <h1 className="mt-2 font-serif text-3xl leading-tight font-semibold tracking-tight text-ink sm:text-4xl">
        {section.title}
      </h1>
      {section.summary && <p className="mt-3 text-lg text-ink-muted">{section.summary}</p>}
      <p className="mt-3 text-xs text-ink-subtle">
        Section {section.position + 1} of {course.sections.length} · {depthLabel(course.depth)} ·{" "}
        {styleLabel(course.learning_style)}
      </p>
    </header>
  );
}

function MarginSummary({
  count,
  resolved,
  showResolved,
  onToggleResolved,
}: {
  count: number;
  resolved: number;
  showResolved: boolean;
  onToggleResolved: () => void;
}) {
  return (
    <p className="mb-8 flex flex-wrap items-center gap-x-3 gap-y-1 border-y border-line py-2.5 text-sm text-ink-subtle">
      <span>
        {count > 0
          ? `${plural(count, "margin note")} on this section.`
          : "Select any passage to ask the tutor about it."}
      </span>
      {resolved > 0 && (
        <button type="button" onClick={onToggleResolved} className="text-brand-ink hover:underline">
          {showResolved ? "Hide" : "Show"} {resolved} resolved
        </button>
      )}
    </p>
  );
}

function SectionBody({ section }: { section: Section }) {
  const retry = useSectionMutation(() => api.generateSection(section.id));
  return (
    <div className="space-y-7">
      {section.blocks.map((block) => (
        <div key={block.id} data-block-id={block.id} className="scroll-mt-24">
          <BlockView block={block} />
        </div>
      ))}
      {isWriting(section) && <WritingProgress section={section} />}
      {section.status === "failed" && (
        <ErrorNotice
          title="This section couldn't be written"
          message={section.error ?? "Something went wrong."}
          action={
            <Button size="sm" onClick={() => retry.mutate(undefined)} loading={retry.isPending}>
              Try again
            </Button>
          }
        />
      )}
    </div>
  );
}

function WritingProgress({ section }: { section: Section }) {
  const stage = section.stage ?? "queued";
  const started = section.blocks.length > 0;
  const description =
    stage === "researching"
      ? "Looking up accurate, current sources to ground this section."
      : stage === "writing"
        ? started
          ? "More is on its way. Each part appears as soon as it's finished."
          : "Writing this section for you now. Each part appears as soon as it's finished."
        : "This section is written just for you, right when you need it.";
  return (
    <div role="status" className="rounded-xl border border-line bg-surface p-5">
      <div className="flex items-center gap-3 text-sm font-medium text-ink">
        <Spinner className="size-4 text-brand-ink" />
        {STAGE_LABELS[stage]}
        {section.research && stage === "writing" && (
          <Badge tone="brand">{plural(section.research.sources.length, "source")}</Badge>
        )}
      </div>
      <p className="mt-1 text-sm text-ink-muted">{description}</p>
      {!started && (
        <div className="mt-5 animate-pulse space-y-3" aria-hidden>
          <div className="h-3 w-11/12 rounded bg-sunken" />
          <div className="h-3 w-full rounded bg-sunken" />
          <div className="h-3 w-4/5 rounded bg-sunken" />
          <div className="h-3 w-2/3 rounded bg-sunken" />
        </div>
      )}
    </div>
  );
}

function SectionFooter({ course, section }: { course: Course; section: Section }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const progress = useSectionMutation((completed: boolean) => api.setProgress(section.id, completed));
  const rewrite = useSectionMutation(() => api.generateSection(section.id, true));
  const isLast = !section.next_section_id;

  function completeAndContinue() {
    progress.mutate(true, {
      onSuccess: () => {
        if (section.next_section_id) navigate(`/courses/${course.id}/learn/${section.next_section_id}`);
      },
    });
  }

  function rewriteSection() {
    const message =
      "Rewrite this section from scratch? Its margin notes will be removed, because they point at the current text.";
    if (!window.confirm(message)) return;
    rewrite.mutate(undefined, {
      onSuccess: () => void queryClient.invalidateQueries({ queryKey: queryKeys.threads(section.id) }),
    });
  }

  return (
    <footer className="mt-12 space-y-8 border-t border-line pt-8">
      {section.research && section.research.sources.length > 0 && (
        <Sources research={section.research} />
      )}
      <div className="flex flex-wrap items-center gap-3">
        {section.previous_section_id && (
          <Link
            to={`/courses/${course.id}/learn/${section.previous_section_id}`}
            className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-ink-muted hover:bg-surface-hover hover:text-ink"
          >
            <ArrowLeft className="size-4" aria-hidden />
            Previous
          </Link>
        )}
        <div className="ml-auto flex flex-wrap items-center gap-2">
          {section.completed_at ? (
            <>
              <Badge tone="positive">
                <Check className="size-3.5" aria-hidden />
                Completed
              </Badge>
              {!isLast && (
                <Button onClick={() => navigate(`/courses/${course.id}/learn/${section.next_section_id}`)}>
                  Next section
                  <ArrowRight className="size-4" aria-hidden />
                </Button>
              )}
            </>
          ) : (
            <Button onClick={completeAndContinue} loading={progress.isPending}>
              {isLast ? "Finish the course" : "Mark complete and continue"}
              {!isLast && <ArrowRight className="size-4" aria-hidden />}
            </Button>
          )}
        </div>
      </div>
      <button
        type="button"
        onClick={rewriteSection}
        className="inline-flex items-center gap-1.5 text-xs text-ink-subtle hover:text-ink"
      >
        <RefreshCw className="size-3.5" aria-hidden />
        Rewrite this section
      </button>
    </footer>
  );
}

function Sources({ research }: { research: ResearchNotes }) {
  return (
    <section aria-labelledby="sources">
      <h2 id="sources" className="text-sm font-semibold tracking-wide text-ink-subtle uppercase">
        Sources
      </h2>
      <ul className="mt-3 space-y-1.5">
        {research.sources.map((source) => (
          <li key={source.url}>
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-start gap-1.5 text-sm text-ink-muted hover:text-brand-ink"
            >
              <ExternalLink className="mt-0.5 size-3.5 shrink-0" aria-hidden />
              {source.title}
            </a>
          </li>
        ))}
      </ul>
      <details className="mt-4 rounded-xl border border-line bg-surface px-4 py-3">
        <summary className="cursor-pointer text-sm font-medium text-ink-muted">Research notes</summary>
        <Markdown compact className="mt-3 text-ink-muted">
          {research.notes}
        </Markdown>
      </details>
    </section>
  );
}
