import json

import pytest

from app.course.schemas import (
    CoursePlanDraft,
    DiagnosticQuizDraft,
    OutlineDraft,
    SectionDraft,
)
from app.llm import client as llm_client
from app.llm.base import LLMRequest, Message
from app.llm.prompts import render_prompt
from app.llm.providers.fake import FakeProvider
from app.settings import settings

PROFILE = {
    "level": "beginner",
    "summary": "New to statistics.",
    "strengths": ["Arithmetic"],
    "gaps": ["Conditional probability"],
}
OUTLINE = [
    {
        "id": "m1",
        "title": "Foundations",
        "summary": "",
        "sections": [{"id": "s1", "title": "Probability as belief", "summary": "Basics."}],
    }
]


@pytest.mark.parametrize(
    ("task", "schema", "meta"),
    [
        ("diagnostics", DiagnosticQuizDraft, {"goal": "learn Bayesian statistics"}),
        ("plan", CoursePlanDraft, {"goal": "learn Bayesian statistics", "depth": "overview"}),
        ("outline", OutlineDraft, {"goal": "Bayes", "instructions": "make it shorter"}),
        ("section", SectionDraft, {"section_title": "Priors", "style": "visual"}),
    ],
)
async def test_fake_provider_writes_valid_structured_responses(task, schema, meta):
    provider = FakeProvider()
    request = LLMRequest(task=task, system="s", messages=[Message("user", "u")], meta=meta)
    partials: list[str] = []

    async def on_partial(text: str):
        partials.append(text)

    result = await provider.generate(request, schema, on_partial)

    assert isinstance(result, schema)
    assert partials and json.loads(partials[-1]) == result.model_dump(mode="json")
    assert provider.requests == [request]


def test_structured_output_schemas_avoid_const():
    # One-item enums are accepted by every provider's schema subset; "const" is not
    for schema in (DiagnosticQuizDraft, CoursePlanDraft, OutlineDraft, SectionDraft):
        assert '"const"' not in json.dumps(schema.model_json_schema())


@pytest.mark.parametrize(
    ("template", "context", "expected"),
    [
        (
            "diagnostics",
            {"goal": "Bayes", "depth": "rigorous", "style": "visual", "background": "Physics"},
            ["Rigorous:", "Visual learner", "Physics"],
        ),
        (
            "plan",
            {
                "goal": "Bayes",
                "depth": "overview",
                "style": "hands_on",
                "background": "",
                "sizing": "3 to 4 modules",
                "answers": [
                    {
                        "question": "What is a prior?",
                        "answer": "A belief before evidence",
                        "correct_answer": "A belief before evidence",
                        "is_correct": True,
                    }
                ],
            },
            ["3 to 4 modules", "Hands-on learner", "What is a prior?", "(correct)"],
        ),
        (
            "outline",
            {
                "goal": "Bayes",
                "depth": "practitioner",
                "style": "reading",
                "profile": PROFILE,
                "sizing": "4 to 5 modules",
                "title": "Bayes for beginners",
                "modules": OUTLINE,
                "instructions": "More examples",
            },
            ["Bayes for beginners", "Probability as belief", "More examples", "beginner"],
        ),
        (
            "section",
            {
                "depth": "practitioner",
                "style": "intuition",
                "profile": PROFILE,
                "length": "900 to 1,400",
                "course_title": "Bayes",
                "course_description": "A course.",
                "goal": "Bayes",
                "outline": OUTLINE,
                "section_id": "s1",
                "recaps": [{"title": "Earlier", "recap": "Covered counting."}],
                "research_notes": "- A fact.",
                "section_title": "Probability as belief",
                "section_summary": "Basics.",
            },
            ["<- the section to write now", "Covered counting.", "<research_notes>", "Intuition"],
        ),
    ],
)
def test_prompt_templates_render(template, context, expected):
    system, user = render_prompt(template, **context)
    combined = system + "\n" + user
    for text in expected:
        assert text in combined
    assert system and user


async def test_identical_requests_are_served_from_the_cache(monkeypatch):
    provider = FakeProvider()
    llm_client.set_llm(provider)
    monkeypatch.setattr(settings, "LLM_CACHE", True)
    request = LLMRequest(
        task="diagnostics",
        system="cache test",
        messages=[Message("user", "u")],
        meta={"goal": "learn caching"},
    )
    try:
        first = await llm_client.generate(request, DiagnosticQuizDraft)
        second = await llm_client.generate(request, DiagnosticQuizDraft)
        uncached = await llm_client.generate(request, DiagnosticQuizDraft, use_cache=False)
    finally:
        llm_client.set_llm(None)

    assert first == second == uncached
    assert len(provider.requests) == 2  # The second call never reached the provider
