import asyncio
import json
import uuid
from datetime import timedelta

from sqlmodel import update

from app import jobs
from app.course.generation import PartialSectionWriter, claim_section, generate_section
from app.course.models import Section
from app.db.base_model import get_utc_now
from app.db.session import get_session
from app.llm import set_llm
from app.llm.exceptions import LLMConfigurationError, LLMError
from app.llm.providers.fake import FakeProvider
from tests.helpers import create_course, plan_course, start_course


def section_ids(course: dict) -> list[str]:
    return [s["id"] for module in course["outline"] for s in module["sections"]]


async def test_create_course_writes_diagnostic_questions_without_answers(client, fake_llm):
    course = await create_course(client, background="I took a statistics class years ago")

    assert course["status"] == "diagnostic"
    assert 3 <= len(course["diagnostics"]) <= 4
    question = course["diagnostics"][0]
    assert question["id"] and question["options"]
    assert "correct_option" not in question  # The answers stay on the server
    request = fake_llm.requests[0]
    assert request.task == "diagnostics" and request.effort == "low"
    assert "I took a statistics class years ago" in request.messages[0].content


async def test_answers_produce_a_learner_profile_and_an_outline(client, fake_llm):
    course = await plan_course(client)

    assert course["profile"]["level"] in {"beginner", "intermediate", "advanced"}
    assert course["title"] and course["description"]
    assert len(course["outline"]) == 3
    assert all(len(module["sections"]) == 3 for module in course["outline"])
    assert all(uuid.UUID(section_id) for section_id in section_ids(course))
    assert course["sections"] == []  # Nothing is written before the learner starts
    plan_request = fake_llm.requests[-1]
    assert plan_request.task == "plan"
    assert "Their answer:" in plan_request.messages[0].content


async def test_skipping_the_diagnostic_still_plans_a_course(client, fake_llm):
    course = await create_course(client, depth="overview")
    response = await client.post(f"/api/courses/{course['id']}/answers", json={"answers": []})
    assert response.json()["status"] == "planning"
    await jobs.drain()

    course = (await client.get(f"/api/courses/{course['id']}")).json()
    assert course["status"] == "outline_ready"
    assert "skipped the diagnostic" in fake_llm.requests[-1].messages[0].content


async def test_outline_edits_are_saved_and_new_items_get_ids(client):
    course = await plan_course(client)
    first, second = course["outline"][0], course["outline"][1]
    edited = {
        "title": "  My Bayes course  ",
        "description": "Edited",
        "modules": [
            # Reordered, renamed, one section removed and one added without an id
            {
                "id": second["id"],
                "title": "Mechanics first",
                "sections": [
                    second["sections"][1],
                    {"title": "A section I added", "summary": "Mine"},
                ],
            },
            {"id": first["id"], "title": first["title"], "sections": first["sections"][:1]},
        ],
    }

    response = await client.put(f"/api/courses/{course['id']}/outline", json=edited)

    assert response.status_code == 200, response.text
    outline = response.json()["outline"]
    assert response.json()["title"] == "My Bayes course"
    assert [m["title"] for m in outline] == ["Mechanics first", first["title"]]
    assert outline[0]["sections"][0]["id"] == second["sections"][1]["id"]
    added = outline[0]["sections"][1]
    assert added["title"] == "A section I added" and uuid.UUID(added["id"])


async def test_outline_validation_rejects_empty_titles_and_modules(client):
    course = await plan_course(client)
    bad = {"title": "   ", "modules": [{"title": "M", "sections": []}]}

    response = await client.put(f"/api/courses/{course['id']}/outline", json=bad)

    assert response.status_code == 422


async def test_outline_revision_follows_the_learners_instructions(client, fake_llm):
    course = await plan_course(client)

    response = await client.post(
        f"/api/courses/{course['id']}/outline/revise", json={"instructions": "Make it shorter"}
    )
    assert response.json()["status"] == "planning"
    await jobs.drain()

    revised = (await client.get(f"/api/courses/{course['id']}")).json()
    assert revised["status"] == "outline_ready"
    assert len(section_ids(revised)) < len(section_ids(course))
    assert "Make it shorter" in fake_llm.requests[-1].messages[0].content


async def test_starting_writes_only_the_first_section(client, fake_llm):
    course = await start_course(client)

    assert course["status"] == "in_progress"
    statuses = [s["status"] for s in course["sections"]]
    assert statuses[0] == "ready"
    assert set(statuses[1:]) == {"pending"}  # Just in time: the rest wait until opened
    assert course["current_section_id"] == course["sections"][0]["id"]
    assert [s["title"] for s in course["sections"]] == [
        s["title"] for m in course["outline"] for s in m["sections"]
    ]
    response = await client.put(f"/api/courses/{course['id']}/outline", json={})
    assert response.status_code in (409, 422)


async def test_written_sections_have_typed_blocks_and_research_notes(client, fake_llm):
    course = await start_course(client, learning_style="visual")

    section = (await client.get(f"/api/sections/{course['sections'][0]['id']}")).json()

    assert section["status"] == "ready" and section["stage"] is None
    types = [block["type"] for block in section["blocks"]]
    assert {"text", "diagram", "callout", "example", "exercise"} <= set(types)
    assert len({block["id"] for block in section["blocks"]}) == len(types)
    assert section["research"]["notes"]
    assert section["research"]["sources"][0]["url"].startswith("https://")
    assert section["previous_section_id"] is None
    assert section["next_section_id"] == course["sections"][1]["id"]
    tasks = [r.task for r in fake_llm.requests]
    assert tasks[-2:] == ["research", "section"]
    writing = fake_llm.requests[-1].messages[0].content
    assert "<research_notes>" in writing and "<- the section to write now" in writing


async def test_opening_a_section_writes_it_and_prefetches_the_next(client):
    course = await start_course(client)
    second, third, fourth = course["sections"][1:4]

    response = await client.post(f"/api/sections/{second['id']}/open")
    assert response.status_code == 200
    await jobs.drain()

    course = (await client.get(f"/api/courses/{course['id']}")).json()
    statuses = {s["id"]: s["status"] for s in course["sections"]}
    assert statuses[second["id"]] == "ready"
    assert statuses[third["id"]] == "ready"  # Prefetched
    assert statuses[fourth["id"]] == "pending"
    assert course["current_section_id"] == second["id"]


async def test_later_sections_are_told_what_earlier_ones_covered(client, fake_llm):
    course = await start_course(client)

    await client.post(f"/api/sections/{course['sections'][1]['id']}/open")
    await jobs.drain()

    second_prompt = next(
        r.messages[0].content
        for r in fake_llm.requests
        if r.task == "section" and r.meta["section_title"] == course["sections"][1]["title"]
    )
    assert "What earlier sections covered:" in second_prompt


async def test_a_failed_section_reports_the_error_and_can_be_retried(client):
    course = await start_course(client)
    section_id = course["sections"][1]["id"]

    class FailingProvider(FakeProvider):
        async def generate(self, request, schema, on_partial=None):
            raise LLMError("Claude is overloaded. Try again shortly.")

    set_llm(FailingProvider())
    await client.post(f"/api/sections/{section_id}/open")
    await jobs.drain()
    failed = (await client.get(f"/api/sections/{section_id}")).json()
    assert failed["status"] == "failed"
    assert failed["error"] == "Claude is overloaded. Try again shortly."

    set_llm(FakeProvider())
    response = await client.post(f"/api/sections/{section_id}/generate", json={})
    assert response.status_code == 202
    await jobs.drain()
    assert (await client.get(f"/api/sections/{section_id}")).json()["status"] == "ready"


async def test_regenerating_a_written_section_replaces_its_blocks(client, fake_llm):
    course = await start_course(client)
    section_id = course["sections"][0]["id"]
    before = (await client.get(f"/api/sections/{section_id}")).json()

    response = await client.post(f"/api/sections/{section_id}/generate", json={})
    assert response.status_code == 409  # Already written; must ask to regenerate

    response = await client.post(f"/api/sections/{section_id}/generate", json={"regenerate": True})
    assert response.status_code == 202
    await jobs.drain()

    after = (await client.get(f"/api/sections/{section_id}")).json()
    assert after["status"] == "ready"
    assert {b["id"] for b in after["blocks"]}.isdisjoint({b["id"] for b in before["blocks"]})


async def test_only_one_writer_can_claim_a_section(client, fake_llm):
    course = await start_course(client)
    section_id = uuid.UUID(course["sections"][2]["id"])

    await asyncio.gather(*(generate_section(section_id) for _ in range(3)))

    writes = [r for r in fake_llm.requests if r.task == "section"]
    titles = [r.meta["section_title"] for r in writes]
    assert titles.count(course["sections"][2]["title"]) == 1


async def test_a_stale_generating_section_can_be_claimed_again(client):
    course = await start_course(client)
    section_id = uuid.UUID(course["sections"][3]["id"])
    assert await claim_section(section_id)
    assert not await claim_section(section_id)  # Being written

    async with get_session() as db:
        await db.exec(
            update(Section)
            .where(Section.id == section_id)
            .values(generation_started_at=get_utc_now() - timedelta(hours=1))
        )
        await db.commit()

    assert await claim_section(section_id)  # Its writer must have died


def test_partial_writer_keeps_only_blocks_that_have_finished_streaming():
    writer = PartialSectionWriter(uuid.uuid4())
    full = {
        "blocks": [
            {"type": "text", "markdown": "First paragraph."},
            {"type": "callout", "variant": "tip", "title": "Tip", "markdown": "Remember."},
        ],
        "recap": "Covered things.",
    }
    text = json.dumps(full)

    halfway = text[: text.index('"Remember')]
    assert [b["type"] for b in writer.complete_blocks(halfway)] == ["text"]
    second_done = text[: text.index('"recap"') - 2]
    assert [b["type"] for b in writer.complete_blocks(second_done)] == ["text"]
    blocks = writer.complete_blocks(text)
    assert [b["type"] for b in blocks] == ["text", "callout"]
    # Ids stay stable between partial and final saves
    assert blocks[0]["id"] == writer.complete_blocks(halfway)[0]["id"]


async def test_sections_stream_into_the_database_while_being_written(client):
    course = await start_course(client)
    section_id = course["sections"][4]["id"]
    seen: list[int] = []
    PartialSectionWriter.parse_interval = 0
    original_update = PartialSectionWriter.on_partial

    async def spy(self, text):
        await original_update(self, text)
        async with get_session() as db:
            section = await db.get(Section, uuid.UUID(section_id))
            if section.status == "generating":
                seen.append(len(section.blocks))

    PartialSectionWriter.on_partial = spy
    try:
        await generate_section(uuid.UUID(section_id))
    finally:
        PartialSectionWriter.on_partial = original_update
        PartialSectionWriter.parse_interval = 0.4

    assert seen and max(seen) >= 2  # Blocks appeared before the section was finished
    assert seen == sorted(seen)


async def test_progress_and_the_course_list(client):
    course = await start_course(client)
    section_id = course["sections"][0]["id"]

    response = await client.put(f"/api/sections/{section_id}/progress", json={"completed": True})
    assert response.json()["completed_at"] is not None

    listed = next(c for c in (await client.get("/api/courses")).json() if c["id"] == course["id"])
    assert listed["sections_completed"] == 1
    assert listed["sections_total"] == len(course["sections"])


async def test_deleting_a_course_removes_everything(client):
    course = await start_course(client)

    assert (await client.delete(f"/api/courses/{course['id']}")).status_code == 204

    assert (await client.get(f"/api/courses/{course['id']}")).status_code == 404
    assert (await client.get(f"/api/sections/{course['sections'][0]['id']}")).status_code == 404


async def test_planning_failure_can_be_retried(client):
    class BrokenPlanner(FakeProvider):
        async def generate(self, request, schema, on_partial=None):
            if request.task == "plan":
                raise LLMError("The model returned an error (500). Try again shortly.")
            return await super().generate(request, schema, on_partial)

    set_llm(BrokenPlanner())
    course = await create_course(client)
    await client.post(f"/api/courses/{course['id']}/answers", json={"answers": []})
    await jobs.drain()
    failed = (await client.get(f"/api/courses/{course['id']}")).json()
    assert failed["status"] == "planning_failed" and "500" in failed["error"]

    set_llm(FakeProvider())
    await client.post(f"/api/courses/{course['id']}/plan/retry")
    await jobs.drain()
    assert (await client.get(f"/api/courses/{course['id']}")).json()["status"] == "outline_ready"


async def test_model_errors_map_to_helpful_http_errors(client):
    class Unconfigured(FakeProvider):
        async def generate(self, request, schema, on_partial=None):
            raise LLMConfigurationError("No Anthropic credentials found.")

    set_llm(Unconfigured())
    response = await client.post("/api/courses", json={"goal": "learn chess"})

    assert response.status_code == 503
    assert response.json() == {"detail": "No Anthropic credentials found."}


async def test_unknown_ids_return_404(client):
    missing = uuid.uuid4()
    assert (await client.get(f"/api/courses/{missing}")).status_code == 404
    assert (await client.post(f"/api/sections/{missing}/open")).status_code == 404


async def test_config_reports_demo_mode(client):
    config = (await client.get("/api/config")).json()
    assert config == {"provider": "fake", "model": "fake-tutor-1", "research": True, "demo": True}
    assert (await client.get("/api/health")).json()["status"] == "ok"
