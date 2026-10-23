import re

from sqlmodel import select

from app.cli import build_parser
from app.course.blocks import block_adapter
from app.course.demo import load_demo_course
from app.course.export import course_markdown
from app.course.models import Section
from app.db.session import get_session
from app.settings import settings


async def test_cli_generates_a_whole_course_end_to_end(tmp_path, fake_llm, capsys, monkeypatch):
    monkeypatch.setattr(settings, "LLM_CACHE", False)  # The CLI turns the cache on; undo that
    out = tmp_path / "course.md"
    args = build_parser().parse_args(
        [
            "generate",
            "learn chess openings",
            "--depth",
            "overview",
            "--style",
            "hands_on",
            "--no-quiz",
            "--out",
            str(out),
        ]
    )

    assert await args.handler(args) == 0

    markdown = out.read_text()
    assert markdown.startswith("# Chess openings")
    assert settings.LLM_CACHE  # Re-running the same course reuses stored responses
    assert "*Not written yet.*" not in markdown  # Every section was written
    assert markdown.count("```python") == 6  # One code block per section (3 modules x 2)
    assert "**Sources**" in markdown
    assert [r.task for r in fake_llm.requests][:2] == ["diagnostics", "plan"]
    assert "Saved as course" in capsys.readouterr().err


async def test_cli_can_stop_after_a_few_sections(tmp_path, fake_llm, monkeypatch):
    monkeypatch.setattr(settings, "LLM_CACHE", False)
    out = tmp_path / "course.md"
    args = build_parser().parse_args(
        ["generate", "learn knots", "--no-quiz", "--max-sections", "2", "--out", str(out)]
    )

    assert await args.handler(args) == 0

    markdown = out.read_text()
    assert markdown.count("*Not written yet.*") == 7  # 9 sections, 2 written


async def test_demo_course_loads_with_written_sections_and_a_thread(client):
    response = await client.post("/api/courses/demo")
    assert response.status_code == 201
    course = response.json()

    statuses = [s["status"] for s in course["sections"]]
    assert statuses == ["ready"] * 4 + ["pending"] * 2
    assert course["profile"]["level"] == "intermediate"

    base_rates = course["sections"][3]
    threads = (await client.get(f"/api/sections/{base_rates['id']}/threads")).json()
    assert len(threads) == 1 and len(threads[0]["messages"]) == 2
    section = (await client.get(f"/api/sections/{base_rates['id']}")).json()
    block = next(b for b in section["blocks"] if b["id"] == threads[0]["block_id"])
    thread = threads[0]
    # The anchor must really occur in the block, with its prefix and suffix around it
    assert thread["prefix"] + thread["quote"] + thread["suffix"] in block["markdown"]


async def test_demo_course_blocks_are_valid_and_export_cleanly():
    async with get_session() as db:
        course = await load_demo_course(db)
        sections = (await db.exec(select(Section).where(Section.course_id == course.id))).all()
        markdown = await course_markdown(db, course)

    for section in sections:
        for block in section.blocks:
            block_adapter.validate_python(block)
    assert "$$P(A \\mid B) = \\frac{P(B \\mid A)\\,P(A)}{P(B)}$$" in markdown
    assert len(re.findall(r"```mermaid", markdown)) == 4
