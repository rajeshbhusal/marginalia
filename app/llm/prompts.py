from functools import cache

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.settings import settings


@cache
def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(settings.PROMPT_TEMPLATE_DIR),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
    )


def render_prompt(template_name: str, **context) -> tuple[str, str]:
    """Render a prompt template's `system` and `user` blocks.

    Each task has one template in app/llm/templates that defines both blocks, so the instructions
    and the per-request input live side by side.
    """
    template = _environment().get_template(f"{template_name}.jinja")
    template_context = template.new_context(context)
    system = "".join(template.blocks["system"](template_context)).strip()
    user = "".join(template.blocks["user"](template_context)).strip()
    return system, user
