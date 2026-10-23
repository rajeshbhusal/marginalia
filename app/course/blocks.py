"""Content blocks: the typed pieces a section is written as."""

from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from app.llm.schema import DraftModel
from app.util import short_id


class TextBlockDraft(DraftModel):
    type: Literal["text"]
    markdown: str = Field(
        description="Explanation in GitHub-flavoured markdown. Inline maths in $...$, display "
        "maths in $$...$$. Use ### or smaller for any subheadings."
    )


class CodeBlockDraft(DraftModel):
    type: Literal["code"]
    language: str = Field(description="Language for syntax highlighting, e.g. python or sql.")
    code: str = Field(description="Complete, runnable code with brief comments.")
    caption: str = Field(description="One sentence on what the code shows, or an empty string.")


class DiagramBlockDraft(DraftModel):
    type: Literal["diagram"]
    mermaid: str = Field(
        description="Mermaid source for one simple diagram (flowchart, sequenceDiagram, "
        "classDiagram, stateDiagram-v2, mindmap or timeline). Put labels in double quotes and "
        "don't use markdown or maths inside labels."
    )
    caption: str = Field(description="One sentence explaining what the diagram shows.")


class ExampleBlockDraft(DraftModel):
    type: Literal["example"]
    title: str
    markdown: str = Field(description="A worked example in markdown, step by step.")


class ExerciseBlockDraft(DraftModel):
    type: Literal["exercise"]
    prompt: str = Field(description="The task for the learner, in markdown.")
    hints: list[str] = Field(description="One to three progressively stronger hints.")
    solution: str = Field(description="A complete worked solution in markdown.")


class CalloutBlockDraft(DraftModel):
    type: Literal["callout"]
    variant: Literal["key_idea", "definition", "tip", "warning"]
    title: str
    markdown: str


BlockDraft = (
    TextBlockDraft
    | CodeBlockDraft
    | DiagramBlockDraft
    | ExampleBlockDraft
    | ExerciseBlockDraft
    | CalloutBlockDraft
)


class TextBlock(TextBlockDraft):
    id: str


class CodeBlock(CodeBlockDraft):
    id: str


class DiagramBlock(DiagramBlockDraft):
    id: str


class ExampleBlock(ExampleBlockDraft):
    id: str


class ExerciseBlock(ExerciseBlockDraft):
    id: str


class CalloutBlock(CalloutBlockDraft):
    id: str


Block = Annotated[
    TextBlock | CodeBlock | DiagramBlock | ExampleBlock | ExerciseBlock | CalloutBlock,
    Field(discriminator="type"),
]

block_draft_adapter: TypeAdapter[BlockDraft] = TypeAdapter(BlockDraft)
block_adapter: TypeAdapter[Block] = TypeAdapter(Block)


def new_block_id() -> str:
    return short_id("b")


def with_id(draft: BlockDraft, block_id: str) -> Block:
    return block_adapter.validate_python({**draft.model_dump(), "id": block_id})


CALLOUT_LABELS = {
    "key_idea": "Key idea",
    "definition": "Definition",
    "tip": "Tip",
    "warning": "Watch out",
}


def render_block_markdown(block: BlockDraft, include_solutions: bool = True) -> str:
    """Render a block as plain markdown, for prompts and Markdown exports."""
    match block.type:
        case "text":
            return block.markdown.strip()
        case "code":
            code = f"```{block.language}\n{block.code.rstrip()}\n```"
            return f"{code}\n\n*{block.caption.strip()}*" if block.caption.strip() else code
        case "diagram":
            diagram = f"```mermaid\n{block.mermaid.strip()}\n```"
            return f"{diagram}\n\n*{block.caption.strip()}*" if block.caption.strip() else diagram
        case "example":
            return f"**Example: {block.title.strip()}**\n\n{block.markdown.strip()}"
        case "exercise":
            parts = [f"**Exercise**\n\n{block.prompt.strip()}"]
            if include_solutions:
                parts += [f"*Hint:* {hint.strip()}" for hint in block.hints]
                parts.append(f"**Solution**\n\n{block.solution.strip()}")
            return "\n\n".join(parts)
        case "callout":
            label = CALLOUT_LABELS.get(block.variant, "Note")
            title = block.title.strip()
            heading = f"**{label}: {title}**" if title and title != label else f"**{label}**"
            body = "\n".join(f"> {line}" for line in block.markdown.strip().splitlines())
            return f"> {heading}\n>\n{body}"
    raise ValueError(f"Unknown block type {block.type}")


def render_blocks_markdown(blocks: list[BlockDraft], include_solutions: bool = True) -> str:
    return "\n\n".join(render_block_markdown(b, include_solutions) for b in blocks)
