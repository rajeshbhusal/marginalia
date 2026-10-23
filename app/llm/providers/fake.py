"""An offline stand-in for a real model.

It writes deterministic, clearly generic content shaped like real responses, so tests, CI and
demos run without an API key. Requests are recorded on `requests` for tests to inspect.
"""

import asyncio
import json
import re
from collections.abc import Callable
from typing import Any

from app.llm.base import LLMRequest, PartialCallback, ResearchResult, SchemaT, Source
from app.llm.exceptions import LLMError

STREAM_CHUNKS = 24


class FakeProvider:
    name = "fake"
    supports_web_search = True

    def __init__(self, model: str = "fake-tutor-1", delay: float = 0.0):
        self.model = model
        self.delay = delay
        self.requests: list[LLMRequest] = []

    async def generate(
        self,
        request: LLMRequest,
        schema: type[SchemaT],
        on_partial: PartialCallback | None = None,
    ) -> SchemaT:
        self.requests.append(request)
        builder = STRUCTURED_BUILDERS.get(request.task)
        if builder is None:
            raise LLMError(f"The fake provider can't write a '{request.task}' response.")
        data = builder(request.meta)
        if on_partial is not None:
            text = json.dumps(data)
            step = max(1, len(text) // STREAM_CHUNKS)
            for end in range(step, len(text) + step, step):
                await on_partial(text[:end])
                if self.delay:
                    await asyncio.sleep(self.delay)
        elif self.delay:
            await asyncio.sleep(self.delay * 4)
        return schema.model_validate(data)

    async def generate_text(self, request: LLMRequest) -> str:
        self.requests.append(request)
        if self.delay:
            await asyncio.sleep(self.delay * 4)
        if request.task != "tutor":
            raise LLMError(f"The fake provider can't write a '{request.task}' response.")
        return _tutor_reply(request.meta)

    async def research(self, request: LLMRequest, max_searches: int) -> ResearchResult:
        self.requests.append(request)
        title = request.meta.get("section_title", "this topic")
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        return ResearchResult(
            notes=(
                f"- {title} is usually introduced by first fixing the vocabulary, then showing "
                "one concrete case before generalising.\n"
                "- Learners commonly confuse the mechanism with its outcome; a worked example "
                "that separates the two helps.\n"
                "- (Offline demo mode: these notes are placeholders, not real research.)"
            ),
            sources=[
                Source(
                    title=f"Demo source for {title} (offline mode)",
                    url=f"https://example.org/marginalia-demo/{slug}",
                )
            ],
        )


GOAL_PREAMBLE = re.compile(
    r"^(i\s+(want|would like|need)\s+to\s+)?(learn|understand|get better at|study)\s+(about\s+)?",
    re.IGNORECASE,
)


def _topic(goal: str) -> str:
    topic = GOAL_PREAMBLE.sub("", goal.strip().rstrip(".?!"))
    topic = topic.strip() or goal.strip()
    return topic[0].upper() + topic[1:] if topic else "Your topic"


def _diagnostics(meta: dict[str, Any]) -> dict:
    topic = _topic(meta.get("goal", ""))
    return {
        "questions": [
            {
                "question": f"How would you describe your experience with {topic.lower()}?",
                "options": [
                    "I'm completely new to it",
                    "I've read or watched an introduction",
                    "I've used it in a project",
                    "I use it regularly and want depth",
                ],
                "correct_option": None,
                "concept": "Self-assessed experience",
            },
            {
                "question": "Which statement best describes a model in this context?",
                "options": [
                    "A simplified description that captures the important behaviour",
                    "An exact copy of the real system",
                    "A list of facts to memorise",
                ],
                "correct_option": 0,
                "concept": "Models and abstraction",
            },
            {
                "question": "When a result surprises you, what is the most useful first step?",
                "options": [
                    "Check the assumptions behind it",
                    "Ignore it as noise",
                    "Repeat it until it changes",
                ],
                "correct_option": 0,
                "concept": "Reasoning about evidence",
            },
            {
                "question": "How comfortable are you reading short formulas or code snippets?",
                "options": ["Not at all", "Somewhat", "Very comfortable"],
                "correct_option": None,
                "concept": "Comfort with notation",
            },
        ]
    }


MODULE_TEMPLATES = [
    (
        "Foundations of {topic}",
        "The vocabulary and core ideas everything else builds on.",
        [
            ("What {topic} is and why it matters", "A plain-language definition and its uses."),
            ("The core vocabulary", "The handful of terms you'll meet everywhere."),
            ("A first worked example", "One small case, worked end to end."),
        ],
    ),
    (
        "How {topic} works",
        "The mechanism underneath, from intuition to detail.",
        [
            ("The key mechanism", "What actually happens, step by step."),
            ("Building intuition with a model", "A simple model that predicts the behaviour."),
            ("Common misconceptions", "Mistakes learners often make, and why."),
        ],
    ),
    (
        "{topic} in practice",
        "Using what you've learned on realistic problems.",
        [
            ("A step-by-step walkthrough", "A realistic task, solved carefully."),
            ("Tools and techniques", "The methods practitioners reach for."),
            ("Troubleshooting and pitfalls", "Diagnosing what goes wrong."),
        ],
    ),
    (
        "Going deeper",
        "Precise definitions and the reasoning behind the results.",
        [
            ("Formal definitions", "The ideas stated precisely."),
            ("Derivations and proofs", "Why the key results hold."),
            ("Open questions and further reading", "Where to go next."),
        ],
    ),
]

SHAPE_BY_DEPTH = {"overview": (3, 2), "practitioner": (3, 3), "rigorous": (4, 3)}


def _modules(topic: str, depth: str, shorter: bool = False) -> list[dict]:
    module_count, section_count = SHAPE_BY_DEPTH.get(depth, (3, 3))
    if shorter:
        module_count, section_count = max(2, module_count - 1), max(2, section_count - 1)
    return [
        {
            "title": title.format(topic=topic),
            "summary": summary,
            "sections": [
                {"title": s_title.format(topic=topic.lower()), "summary": s_summary}
                for s_title, s_summary in sections[:section_count]
            ],
        }
        for title, summary, sections in MODULE_TEMPLATES[:module_count]
    ]


def _plan(meta: dict[str, Any]) -> dict:
    topic = _topic(meta.get("goal", ""))
    correct = meta.get("correct_answers", 0)
    level = "beginner" if correct <= 1 else "intermediate" if correct == 2 else "advanced"
    return {
        "profile": {
            "level": level,
            "summary": f"Starting point for {topic.lower()}: comfortable with general reasoning, "
            "new to the specifics.",
            "strengths": ["Reasoning about evidence"],
            "gaps": [f"Core vocabulary of {topic.lower()}"],
        },
        "title": topic,
        "description": f"A {meta.get('depth', 'practitioner')} course on {topic.lower()}, "
        f"written for a {meta.get('style', 'reading').replace('_', '-')} learner.",
        "modules": _modules(topic, meta.get("depth", "practitioner")),
    }


def _outline(meta: dict[str, Any]) -> dict:
    topic = _topic(meta.get("goal", ""))
    instructions = meta.get("instructions", "").strip()
    description = f"A {meta.get('depth', 'practitioner')} course on {topic.lower()}."
    if instructions:
        description += f" Revised: {instructions}"
    return {
        "title": meta.get("current_title") or topic,
        "description": description,
        "modules": _modules(
            topic, meta.get("depth", "practitioner"), shorter="short" in instructions.lower()
        ),
    }


def _section(meta: dict[str, Any]) -> dict:
    title = meta.get("section_title", "This section")
    course = meta.get("course_title", "this course")
    style = meta.get("style", "reading")
    depth = meta.get("depth", "practitioner")
    blocks: list[dict] = [
        {
            "type": "text",
            "markdown": f"**{title}** is one of the ideas {course.lower()} rests on. Start with "
            "the intuition: every system worth studying turns some *inputs* into some "
            "*outputs*, and understanding it means being able to predict how changing one "
            "changes the other.\n\nThis demo text was written by Marginalia's offline fake "
            "model, so it is deliberately generic. Connect a real model to get a real lesson.",
        },
        {
            "type": "callout",
            "variant": "key_idea",
            "title": "Key idea",
            "markdown": f"To understand {title.lower()}, separate *what happens* from *why it "
            "happens*, then check your explanation against a concrete case.",
        },
    ]
    if style == "visual":
        blocks.append(
            {
                "type": "diagram",
                "mermaid": 'flowchart LR\n  A["Inputs"] --> B["Mechanism"]\n'
                '  B --> C["Outputs"]\n  C -->|"feedback"| A',
                "caption": "Inputs pass through a mechanism to produce outputs, which feed back.",
            }
        )
    blocks.append(
        {
            "type": "text",
            "markdown": "A compact way to write this down is as a function of the inputs:\n\n"
            "$$\\text{output} = f(\\text{input}_1, \\text{input}_2, \\ldots, \\text{input}_n)$$\n\n"
            "Small changes in one input, $\\Delta x$, lead to a change in the output of roughly "
            "$f'(x)\\,\\Delta x$, which is why sensitivity matters so much in practice.",
        }
    )
    if style == "hands_on" or depth != "overview":
        blocks.append(
            {
                "type": "code",
                "language": "python",
                "code": "def respond(inputs, weights):\n"
                '    """Combine inputs into a single output."""\n'
                "    return sum(x * w for x, w in zip(inputs, weights))\n\n"
                "print(respond([1.0, 2.0], [0.5, 0.25]))  # 1.0",
                "caption": "A tiny model: the output is a weighted sum of the inputs.",
            }
        )
    blocks += [
        {
            "type": "example",
            "title": f"{title} in a small case",
            "markdown": "1. Pick two inputs, say $x_1 = 1$ and $x_2 = 2$.\n"
            "2. Weight them by how much each matters: $0.5$ and $0.25$.\n"
            "3. Combine them: $0.5 \\times 1 + 0.25 \\times 2 = 1$.\n\n"
            "Changing $x_2$ to $4$ raises the output to $1.5$, so the second input matters "
            "half as much per unit as the first.",
        },
        {
            "type": "exercise",
            "prompt": "If the weights were $0.2$ and $0.8$, which input would the output be "
            "most sensitive to, and by how much?",
            "hints": [
                "Compare the weights directly.",
                "The output changes by the weight times the change in the input.",
            ],
            "solution": "The second input: each unit of change in $x_2$ moves the output by "
            "$0.8$, four times the $0.2$ effect of $x_1$.",
        },
    ]
    return {
        "blocks": blocks,
        "recap": f"Introduced {title.lower()} as a mapping from inputs to outputs and showed "
        "how to reason about sensitivity with a worked example.",
    }


def _tutor_reply(meta: dict[str, Any]) -> str:
    quote = meta.get("quote", "this passage").strip()
    question = meta.get("question", "").strip()
    reply = (
        f'Good question. In the passage *"{quote}"*, the important move is to separate the '
        "mechanism from its result.\n\n"
        "Here is another way to see it:\n\n"
        "1. Name the inputs involved.\n"
        "2. Say what the mechanism does to them.\n"
        "3. Check the result against a small example.\n\n"
    )
    if question:
        reply += f"> You asked: {question}\n\n"
    if meta.get("style") == "visual":
        reply += (
            "```mermaid\nflowchart LR\n"
            '  Q["Your question"] --> E["Example"] --> A["Answer"]\n```\n\n'
        )
    reply += "*(Offline demo mode: connect a real model for a real answer.)*"
    return reply


STRUCTURED_BUILDERS: dict[str, Callable[[dict[str, Any]], dict]] = {
    "diagnostics": _diagnostics,
    "plan": _plan,
    "outline": _outline,
    "section": _section,
}
