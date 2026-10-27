"""Command-line tools.

  marginalia generate "how vaccines work" --depth overview --style visual --out course.md
  marginalia demo
  marginalia export <course-id> --out course.md

Courses made here are stored in the database like any other, so you can open them in the app.
"""

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

from sqlmodel import col, select

from app.course import generation, service
from app.course.demo import load_demo_course
from app.course.export import course_markdown
from app.course.models import Course, Section
from app.course.schemas import (
    CourseCreate,
    CourseStatus,
    Depth,
    DiagnosticAnswer,
    LearningStyle,
    SectionStatus,
)
from app.db.session import dispose_engine, get_session
from app.llm import LLMError
from app.settings import settings

APP_URL = "http://localhost:8000"


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def ask_diagnostics(course: Course) -> list[DiagnosticAnswer]:
    answers = []
    log("\nA few quick questions to gauge where to start (Enter = not sure):")
    for question in course.diagnostics:
        log(f"\n{question['question']}")
        for number, option in enumerate(question["options"], start=1):
            log(f"  {number}. {option}")
        reply = input("> ").strip()
        option = int(reply) - 1 if reply.isdigit() else None
        if option is not None and not 0 <= option < len(question["options"]):
            option = None
        answers.append(DiagnosticAnswer(question_id=question["id"], option=option))
    return answers


async def generate(args: argparse.Namespace) -> int:
    """Generate a whole course end to end and print or save it as Markdown."""
    settings.LLM_CACHE = not args.no_cache
    data = CourseCreate(
        goal=args.goal, depth=args.depth, learning_style=args.style, background=args.background
    )
    log(f"Using {settings.LLM_PROVIDER} ({settings.default_model}).")

    async with get_session() as db:
        log("Writing diagnostic questions...")
        course = await service.create_course(db, data)
        quiz = args.quiz if args.quiz is not None else sys.stdin.isatty()
        answers = ask_diagnostics(course) if quiz else []
        await service.submit_answers(db, course, answers)

    log("Planning the course...")
    await service.plan_course(course.id)
    async with get_session() as db:
        course = await service.get_course(db, course.id)
        if course.status != CourseStatus.outline_ready:
            log(f"Planning failed: {course.error}")
            return 1
        for number, module in enumerate(course.outline, start=1):
            log(f"  {number}. {module['title']} ({len(module['sections'])} sections)")
        course = await service.start_course(db, course)
        result = await db.exec(
            select(Section).where(Section.course_id == course.id).order_by(col(Section.position))
        )
        sections = result.all()

    to_write = sections[: args.max_sections] if args.max_sections else sections
    failures = 0
    for number, section in enumerate(to_write, start=1):
        log(f"Writing section {number}/{len(to_write)}: {section.title}")
        await generation.generate_section(section.id)
        async with get_session() as db:
            written = await db.get(Section, section.id)
        if written.status != SectionStatus.ready:
            failures += 1
            log(f"  Failed: {written.error}")

    async with get_session() as db:
        course = await service.get_course(db, course.id)
        markdown = await course_markdown(db, course)
    write_output(markdown, args.out)
    log(f"\nSaved as course {course.id}. Open it in the app: {APP_URL}/courses/{course.id}")
    return 1 if failures else 0


def write_output(markdown: str, out: Path | None) -> None:
    if out:
        out.write_text(markdown, encoding="utf-8")
        log(f"Wrote {out}")
    else:
        sys.stdout.write(markdown)


async def demo(args: argparse.Namespace) -> int:
    async with get_session() as db:
        course = await load_demo_course(db)
    log(f"Loaded the demo course: {APP_URL}/courses/{course.id}")
    return 0


async def export(args: argparse.Namespace) -> int:
    async with get_session() as db:
        course = await service.get_course(db, args.course_id)
        write_output(await course_markdown(db, course), args.out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="marginalia", description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)

    gen = commands.add_parser("generate", help="Generate a whole course end to end")
    gen.add_argument("goal", help='What to learn, e.g. "how vaccines work"')
    gen.add_argument("--depth", choices=[d.value for d in Depth], default=Depth.practitioner)
    gen.add_argument(
        "--style", choices=[s.value for s in LearningStyle], default=LearningStyle.reading
    )
    gen.add_argument("--background", default="", help="What you already know")
    gen.add_argument(
        "--quiz",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Answer the diagnostic questions (default: only when run interactively)",
    )
    gen.add_argument("--max-sections", type=int, default=None, help="Write only the first N")
    gen.add_argument("--out", type=Path, default=None, help="Markdown file (default: stdout)")
    gen.add_argument("--no-cache", action="store_true", help="Don't reuse cached responses")
    gen.set_defaults(handler=generate)

    demo_parser = commands.add_parser("demo", help="Load the demo course (no API key needed)")
    demo_parser.set_defaults(handler=demo)

    exp = commands.add_parser("export", help="Export a course as Markdown")
    exp.add_argument("course_id", type=uuid.UUID)
    exp.add_argument("--out", type=Path, default=None)
    exp.set_defaults(handler=export)
    return parser


async def run(args: argparse.Namespace) -> int:
    try:
        return await args.handler(args)
    except LLMError as e:
        log(f"Error: {e}")
        return 1
    finally:
        await dispose_engine()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
