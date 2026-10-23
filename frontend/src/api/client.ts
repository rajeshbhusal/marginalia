import type {
  AppConfig,
  Course,
  CourseCreate,
  CourseListItem,
  DiagnosticAnswer,
  OutlineUpdate,
  Section,
  Thread,
  ThreadCreate,
} from "./types";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init.headers },
  });
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response));
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      // FastAPI validation errors
      return body.detail.map((item: { msg: string }) => item.msg).join(". ");
    }
  } catch {
    // Not JSON
  }
  return `Something went wrong (${response.status}).`;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) });

export const api = {
  config: () => request<AppConfig>("/config"),

  courses: () => request<CourseListItem[]>("/courses"),
  course: (id: string) => request<Course>(`/courses/${id}`),
  createCourse: (data: CourseCreate) => post<Course>("/courses", data),
  createDemoCourse: () => post<Course>("/courses/demo"),
  deleteCourse: (id: string) => request<void>(`/courses/${id}`, { method: "DELETE" }),
  submitAnswers: (id: string, answers: DiagnosticAnswer[]) =>
    post<Course>(`/courses/${id}/answers`, { answers }),
  retryPlanning: (id: string) => post<Course>(`/courses/${id}/plan/retry`),
  updateOutline: (id: string, outline: OutlineUpdate) =>
    request<Course>(`/courses/${id}/outline`, { method: "PUT", body: JSON.stringify(outline) }),
  reviseOutline: (id: string, instructions: string) =>
    post<Course>(`/courses/${id}/outline/revise`, { instructions }),
  startCourse: (id: string) => post<Course>(`/courses/${id}/start`),

  section: (id: string) => request<Section>(`/sections/${id}`),
  openSection: (id: string) => post<Section>(`/sections/${id}/open`),
  generateSection: (id: string, regenerate = false) =>
    post<Section>(`/sections/${id}/generate`, { regenerate }),
  setProgress: (id: string, completed: boolean) =>
    request<Section>(`/sections/${id}/progress`, {
      method: "PUT",
      body: JSON.stringify({ completed }),
    }),

  threads: (sectionId: string) => request<Thread[]>(`/sections/${sectionId}/threads`),
  createThread: (sectionId: string, data: ThreadCreate) =>
    post<Thread>(`/sections/${sectionId}/threads`, data),
  reply: (threadId: string, content: string) =>
    post<Thread>(`/threads/${threadId}/messages`, { content }),
  resolveThread: (threadId: string, resolved: boolean) =>
    request<Thread>(`/threads/${threadId}`, {
      method: "PATCH",
      body: JSON.stringify({ resolved }),
    }),
  deleteThread: (threadId: string) => request<void>(`/threads/${threadId}`, { method: "DELETE" }),
};
