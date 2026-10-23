import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { Course, Section, Thread, ThreadCreate } from "./types";

export const queryKeys = {
  config: ["config"] as const,
  courses: ["courses"] as const,
  course: (id: string) => ["course", id] as const,
  section: (id: string) => ["section", id] as const,
  threads: (sectionId: string) => ["threads", sectionId] as const,
};

export function isWriting(section: Pick<Section, "status"> | undefined): boolean {
  return section?.status === "pending" || section?.status === "generating";
}

export function useConfig() {
  return useQuery({ queryKey: queryKeys.config, queryFn: api.config, staleTime: Infinity });
}

export function useCourses() {
  return useQuery({ queryKey: queryKeys.courses, queryFn: api.courses });
}

export function useCourse(id: string) {
  return useQuery({
    queryKey: queryKeys.course(id),
    queryFn: () => api.course(id),
    // Poll while the outline is being planned, and slowly while sections are being written
    refetchInterval: (query) => {
      const course = query.state.data;
      if (course?.status === "planning") return 1500;
      if (course?.sections.some((s) => s.status === "generating")) return 3000;
      return false;
    },
  });
}

export function useSection(id: string) {
  return useQuery({
    queryKey: queryKeys.section(id),
    queryFn: () => api.section(id),
    // Sections stream in block by block, so poll quickly while one is being written
    refetchInterval: (query) => (isWriting(query.state.data) ? 1200 : false),
  });
}

/** A mutation that returns the updated course and refreshes the cached copies. */
export function useCourseMutation<TArgs>(mutationFn: (args: TArgs) => Promise<Course>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: (course) => {
      queryClient.setQueryData(queryKeys.course(course.id), course);
      void queryClient.invalidateQueries({ queryKey: queryKeys.courses });
    },
  });
}

/** A mutation that returns the updated section and refreshes the section and its course. */
export function useSectionMutation<TArgs>(mutationFn: (args: TArgs) => Promise<Section>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: (section) => {
      queryClient.setQueryData(queryKeys.section(section.id), section);
      void queryClient.invalidateQueries({ queryKey: queryKeys.course(section.course_id) });
    },
  });
}

export function useThreads(sectionId: string, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.threads(sectionId),
    queryFn: () => api.threads(sectionId),
    enabled,
  });
}

function useThreadCache(sectionId: string) {
  const queryClient = useQueryClient();
  const key = queryKeys.threads(sectionId);
  return {
    upsert(thread: Thread) {
      queryClient.setQueryData<Thread[]>(key, (threads = []) =>
        threads.some((t) => t.id === thread.id)
          ? threads.map((t) => (t.id === thread.id ? thread : t))
          : [...threads, thread],
      );
    },
    remove(threadId: string) {
      queryClient.setQueryData<Thread[]>(key, (threads = []) =>
        threads.filter((t) => t.id !== threadId),
      );
    },
  };
}

export function useCreateThread(sectionId: string) {
  const cache = useThreadCache(sectionId);
  return useMutation({
    mutationFn: (data: ThreadCreate) => api.createThread(sectionId, data),
    onSuccess: cache.upsert,
  });
}

export function useReply(sectionId: string) {
  const cache = useThreadCache(sectionId);
  return useMutation({
    mutationFn: ({ threadId, content }: { threadId: string; content: string }) =>
      api.reply(threadId, content),
    onSuccess: cache.upsert,
  });
}

export function useResolveThread(sectionId: string) {
  const cache = useThreadCache(sectionId);
  return useMutation({
    mutationFn: ({ threadId, resolved }: { threadId: string; resolved: boolean }) =>
      api.resolveThread(threadId, resolved),
    onSuccess: cache.upsert,
  });
}

export function useDeleteThread(sectionId: string) {
  const cache = useThreadCache(sectionId);
  return useMutation({
    mutationFn: (threadId: string) => api.deleteThread(threadId),
    onSuccess: (_result, threadId) => cache.remove(threadId),
  });
}
