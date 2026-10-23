import uuid

from app.llm import set_llm
from app.llm.exceptions import LLMError
from app.llm.providers.fake import FakeProvider
from tests.helpers import start_course


async def ready_section(client) -> dict:
    course = await start_course(client)
    return (await client.get(f"/api/sections/{course['sections'][0]['id']}")).json()


def ask_payload(section: dict, index: int = 1, question: str = "Why does this matter?") -> dict:
    block = section["blocks"][index]
    text = block.get("markdown") or block.get("prompt") or block.get("caption") or ""
    return {
        "block_id": block["id"],
        "quote": text[:40],
        "prefix": "",
        "suffix": text[40:72],
        "question": question,
    }


async def test_highlight_and_ask_creates_an_anchored_thread(client):
    section = await ready_section(client)
    payload = ask_payload(section)

    response = await client.post(f"/api/sections/{section['id']}/threads", json=payload)

    assert response.status_code == 201, response.text
    thread = response.json()
    assert thread["block_id"] == payload["block_id"]
    assert thread["quote"] == payload["quote"] and thread["suffix"] == payload["suffix"]
    assert [m["role"] for m in thread["messages"]] == ["learner", "tutor"]
    assert thread["messages"][0]["content"] == "Why does this matter?"
    assert payload["quote"].strip() in thread["messages"][1]["content"]
    listed = (await client.get(f"/api/sections/{section['id']}/threads")).json()
    assert [t["id"] for t in listed] == [thread["id"]]


async def test_the_tutor_gets_the_passage_its_surroundings_notes_and_learner(client, fake_llm):
    section = await ready_section(client)
    # A text block with two blocks on either side
    index = next(i for i, b in enumerate(section["blocks"]) if b["type"] == "text" and i >= 2)
    assert index + 2 < len(section["blocks"])
    payload = ask_payload(section, index=index, question="Can you draw this?")

    response = await client.post(f"/api/sections/{section['id']}/threads", json=payload)
    assert response.status_code == 201, response.text

    request = fake_llm.requests[-1]
    assert request.task == "tutor" and request.cache_system and request.effort == "low"
    system, question = request.system, request.messages[0].content
    # The whole section, the research notes and the learner profile are in the system prompt
    assert all(f'<block id="{block["id"]}"' in system for block in section["blocks"])
    assert section["research"]["notes"][:40] in system
    assert "Level:" in system and "Visual learner" in system
    # The highlighted passage, its block and the blocks around it come with the question
    assert f"<highlight>{payload['quote']}</highlight>" in question
    assert f'<block id="{payload["block_id"]}">' in question
    blocks = section["blocks"]
    for neighbour in blocks[index - 2 : index] + blocks[index + 1 : index + 3]:
        assert f'<block id="{neighbour["id"]}" position=' in question
    assert question.endswith("My question: Can you draw this?")


async def test_follow_up_questions_carry_the_thread_history(client, fake_llm):
    section = await ready_section(client)
    thread = (
        await client.post(f"/api/sections/{section['id']}/threads", json=ask_payload(section))
    ).json()

    response = await client.post(
        f"/api/threads/{thread['id']}/messages", json={"content": "And in practice?"}
    )

    assert response.status_code == 200
    assert [m["role"] for m in response.json()["messages"]] == [
        "learner",
        "tutor",
        "learner",
        "tutor",
    ]
    messages = fake_llm.requests[-1].messages
    assert [m.role for m in messages] == ["user", "assistant", "user"]
    assert messages[1].content == thread["messages"][1]["content"]
    assert messages[2].content == "And in practice?"


async def test_nothing_is_saved_when_the_tutor_cannot_answer(client):
    section = await ready_section(client)

    class Down(FakeProvider):
        async def generate_text(self, request):
            raise LLMError("Couldn't reach the Anthropic API.")

    set_llm(Down())
    response = await client.post(
        f"/api/sections/{section['id']}/threads", json=ask_payload(section)
    )

    assert response.status_code == 502
    assert (await client.get(f"/api/sections/{section['id']}/threads")).json() == []


async def test_asking_needs_a_written_section_and_a_real_block(client):
    section = await ready_section(client)
    course = (await client.get(f"/api/courses/{section['course_id']}")).json()
    unwritten = course["sections"][3]["id"]
    payload = ask_payload(section)

    response = await client.post(f"/api/sections/{unwritten}/threads", json=payload)
    assert response.status_code == 409

    response = await client.post(
        f"/api/sections/{section['id']}/threads", json=payload | {"block_id": "b_missing"}
    )
    assert response.status_code == 404

    response = await client.post(
        f"/api/sections/{section['id']}/threads", json=payload | {"question": "   "}
    )
    assert response.status_code == 422

    response = await client.post(
        f"/api/sections/{section['id']}/threads", json=payload | {"quote": "  "}
    )
    assert response.status_code == 422


async def test_threads_can_be_resolved_and_deleted(client):
    section = await ready_section(client)
    thread = (
        await client.post(f"/api/sections/{section['id']}/threads", json=ask_payload(section))
    ).json()

    resolved = await client.patch(f"/api/threads/{thread['id']}", json={"resolved": True})
    assert resolved.json()["resolved"] is True

    assert (await client.delete(f"/api/threads/{thread['id']}")).status_code == 204
    assert (
        await client.patch(f"/api/threads/{thread['id']}", json={"resolved": False})
    ).status_code == 404


async def test_regenerating_a_section_removes_its_threads(client):
    section = await ready_section(client)
    await client.post(f"/api/sections/{section['id']}/threads", json=ask_payload(section))

    await client.post(f"/api/sections/{section['id']}/generate", json={"regenerate": True})

    assert (await client.get(f"/api/sections/{section['id']}/threads")).json() == []


async def test_threads_for_unknown_sections_return_404(client):
    assert (await client.get(f"/api/sections/{uuid.uuid4()}/threads")).status_code == 404
