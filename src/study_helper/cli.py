"""Developer Study Helper CLI."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markdown import Markdown

from study_helper import prompts
from study_helper.llm import complete
from study_helper.progress_store import (
    default_progress_path,
    load_progress,
    record_interview_session,
    record_resume_review,
    record_topic,
    summary_dict,
)

app = typer.Typer(
    name="study-helper",
    help="Developer Study Helper: coding Q&A, code gen, errors, interviews, resume, progress.",
    no_args_is_help=True,
)
console = Console()


def _progress_path(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    env = os.environ.get("STUDY_HELPER_PROGRESS")
    if env:
        return Path(env)
    return default_progress_path()


@app.command()
def ask(
    question: Annotated[str, typer.Argument(help="Coding question")],
    topic: Annotated[
        str | None,
        typer.Option("--topic", "-t", help="Tag for progress tracking"),
    ] = None,
    progress_file: Annotated[
        Path | None,
        typer.Option("--progress-file", help="Override progress JSON path"),
    ] = None,
) -> None:
    """Answer a coding question."""
    out = complete(prompts.SYSTEM_ANSWER, question)
    console.print(Markdown(out))
    if topic:
        record_topic(_progress_path(progress_file), topic, note=question[:500])


@app.command("code")
def gen_code(
    spec: Annotated[str, typer.Argument(help="What to build")],
    topic: Annotated[
        str | None,
        typer.Option("--topic", "-t", help="Tag for progress tracking"),
    ] = None,
    progress_file: Annotated[Path | None, typer.Option("--progress-file")] = None,
) -> None:
    """Generate code from a description."""
    out = complete(prompts.SYSTEM_CODE, spec)
    console.print(Markdown(out))
    if topic:
        record_topic(_progress_path(progress_file), topic, note=spec[:500])


@app.command()
def error(
    details: Annotated[str, typer.Argument(help="Error message, stack trace, or paste")],
    topic: Annotated[str | None, typer.Option("--topic", "-t")] = None,
    progress_file: Annotated[Path | None, typer.Option("--progress-file")] = None,
) -> None:
    """Explain an error and suggest fixes."""
    out = complete(prompts.SYSTEM_ERROR, details)
    console.print(Markdown(out))
    if topic:
        record_topic(_progress_path(progress_file), topic)


@app.command("interview")
def interview(
    focus: Annotated[
        str,
        typer.Argument(help="e.g. 'senior Python backend', 'React hooks', 'system design'"),
    ],
    count: Annotated[int, typer.Option("--count", "-n", help="Number of questions")] = 5,
    progress_file: Annotated[Path | None, typer.Option("--progress-file")] = None,
) -> None:
    """Generate interview questions with brief rubrics."""
    user = f"Focus area: {focus}\nGenerate {count} questions."
    out = complete(prompts.SYSTEM_INTERVIEW, user)
    console.print(Markdown(out))
    record_interview_session(_progress_path(progress_file))
    record_topic(_progress_path(progress_file), f"interview:{focus[:80]}")


@app.command()
def resume(
    path: Annotated[
        Path | None,
        typer.Argument(help="Path to resume .txt or .md (optional if using --text)"),
    ] = None,
    text: Annotated[str | None, typer.Option("--text", help="Resume text inline")] = None,
    progress_file: Annotated[Path | None, typer.Option("--progress-file")] = None,
) -> None:
    """Review resume text and give structured feedback."""
    body: str
    if text:
        body = text
    elif path and path.exists():
        body = path.read_text(encoding="utf-8", errors="replace")
    else:
        console.print("[red]Provide a file path or --text with resume content.[/red]")
        raise typer.Exit(code=1)
    out = complete(prompts.SYSTEM_RESUME, body[:120_000])
    console.print(Markdown(out))
    record_resume_review(_progress_path(progress_file))


@app.command()
def progress(
    progress_file: Annotated[Path | None, typer.Option("--progress-file")] = None,
) -> None:
    """Show saved learning progress."""
    path = _progress_path(progress_file)
    state = load_progress(path)
    data = summary_dict(state)
    console.print(f"[bold]Progress file:[/bold] {path}")
    console.print(f"[bold]Streak (consecutive days):[/bold] {data['streak_days']}")
    console.print(f"[bold]Interview sessions:[/bold] {data['interview_sessions']}")
    console.print(f"[bold]Resume reviews:[/bold] {data['resume_reviews']}")
    console.print(f"[bold]Topics tracked:[/bold] {len(data['topics'])}")
    for key, t in sorted(data["topics"].items(), key=lambda x: -x[1].get("sessions", 0)):
        name = t.get("name", key)
        sess = t.get("sessions", 0)
        console.print(f"  - {name} ({sess} sessions)")


if __name__ == "__main__":
    app()
