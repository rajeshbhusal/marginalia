from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.course.blocks import block_adapter, render_blocks_markdown
from app.course.models import Course, Section
from app.course.schemas import SectionStatus


async def course_markdown(db: AsyncSession, course: Course) -> str:
    """The course as one Markdown document: written sections in full, the rest as titles."""
    sections = await db.exec(
        select(Section).where(Section.course_id == course.id).order_by(col(Section.position))
    )
    by_id = {str(section.id): section for section in sections.all()}

    parts = [f"# {course.title}", course.description]
    for module_number, module in enumerate(course.outline, start=1):
        parts.append(f"## {module_number}. {module['title']}")
        for section_number, outline_section in enumerate(module["sections"], start=1):
            parts.append(f"### {module_number}.{section_number} {outline_section['title']}")
            section = by_id.get(outline_section["id"])
            if section is None or section.status != SectionStatus.ready:
                parts.append("*Not written yet.*")
                continue
            blocks = [block_adapter.validate_python(block) for block in section.blocks]
            parts.append(render_blocks_markdown(blocks))
            if section.research and section.research.get("sources"):
                sources = "\n".join(
                    f"- [{source['title']}]({source['url']})"
                    for source in section.research["sources"]
                )
                parts.append(f"**Sources**\n\n{sources}")
    return "\n\n".join(part for part in parts if part.strip()) + "\n"
