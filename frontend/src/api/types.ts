// Mirrors the API schemas in app/course/schemas.py and app/tutor/schemas.py

export type Depth = "overview" | "practitioner" | "rigorous";
export type LearningStyle = "visual" | "reading" | "hands_on" | "intuition";
export type CourseStatus =
  | "diagnostic"
  | "planning"
  | "planning_failed"
  | "outline_ready"
  | "in_progress";
export type SectionStatus = "pending" | "generating" | "ready" | "failed";
export type SectionStage = "queued" | "researching" | "writing";

export interface DiagnosticQuestion {
  id: string;
  question: string;
  options: string[];
  concept: string;
}

export interface DiagnosticAnswer {
  question_id: string;
  option: number | null; // null means "I'm not sure"
}

export interface LearnerProfile {
  level: "beginner" | "intermediate" | "advanced";
  summary: string;
  strengths: string[];
  gaps: string[];
}

export interface OutlineSection {
  id: string;
  title: string;
  summary: string;
}

export interface OutlineModule {
  id: string;
  title: string;
  summary: string;
  sections: OutlineSection[];
}

export interface SectionSummary {
  id: string;
  title: string;
  summary: string;
  position: number;
  module_index: number;
  status: SectionStatus;
  stage: SectionStage | null;
  completed_at: string | null;
}

export interface Course {
  id: string;
  title: string;
  description: string;
  goal: string;
  depth: Depth;
  learning_style: LearningStyle;
  background: string;
  status: CourseStatus;
  error: string | null;
  diagnostics: DiagnosticQuestion[];
  profile: LearnerProfile | null;
  outline: OutlineModule[];
  sections: SectionSummary[];
  current_section_id: string | null;
  model: string;
  created: string;
  updated: string;
}

export interface CourseListItem {
  id: string;
  title: string;
  goal: string;
  depth: Depth;
  learning_style: LearningStyle;
  status: CourseStatus;
  sections_total: number;
  sections_completed: number;
  current_section_id: string | null;
  updated: string;
}

export interface TextBlock {
  id: string;
  type: "text";
  markdown: string;
}
export interface CodeBlock {
  id: string;
  type: "code";
  language: string;
  code: string;
  caption: string;
}
export interface DiagramBlock {
  id: string;
  type: "diagram";
  mermaid: string;
  caption: string;
}
export interface ExampleBlock {
  id: string;
  type: "example";
  title: string;
  markdown: string;
}
export interface ExerciseBlock {
  id: string;
  type: "exercise";
  prompt: string;
  hints: string[];
  solution: string;
}
export interface CalloutBlock {
  id: string;
  type: "callout";
  variant: "key_idea" | "definition" | "tip" | "warning";
  title: string;
  markdown: string;
}
export type Block =
  | TextBlock
  | CodeBlock
  | DiagramBlock
  | ExampleBlock
  | ExerciseBlock
  | CalloutBlock;

export interface ResearchNotes {
  notes: string;
  sources: { title: string; url: string }[];
}

export interface Section {
  id: string;
  course_id: string;
  title: string;
  summary: string;
  position: number;
  module_index: number;
  module_title: string;
  status: SectionStatus;
  stage: SectionStage | null;
  blocks: Block[];
  research: ResearchNotes | null;
  error: string | null;
  generated_at: string | null;
  completed_at: string | null;
  previous_section_id: string | null;
  next_section_id: string | null;
}

export interface ThreadMessage {
  id: string;
  role: "learner" | "tutor";
  content: string;
  created: string;
}

export interface Thread {
  id: string;
  section_id: string;
  block_id: string;
  quote: string;
  prefix: string;
  suffix: string;
  resolved: boolean;
  created: string;
  messages: ThreadMessage[];
}

export interface AppConfig {
  provider: string;
  model: string;
  research: boolean;
  demo: boolean;
}

export interface CourseCreate {
  goal: string;
  depth: Depth;
  learning_style: LearningStyle;
  background: string;
}

export interface OutlineUpdate {
  title: string;
  description: string;
  modules: {
    id?: string;
    title: string;
    summary: string;
    sections: { id?: string; title: string; summary: string }[];
  }[];
}

export interface ThreadCreate {
  block_id: string;
  quote: string;
  prefix: string;
  suffix: string;
  question: string;
}
