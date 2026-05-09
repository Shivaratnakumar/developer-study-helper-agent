"""Developer Study Helper CLI."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markdown import Markdown

from study_helper import prompts
from study_helper.llm import chat, complete
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
    help="Developer Study Helper: coding Q&A, code gen, errors, interviews, mock interview, resume, progress.",
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


@app.command("mock-interview")
def mock_interview(
    focus: Annotated[
        str,
        typer.Argument(help="Role or stack, e.g. 'mid-level Python backend APIs'"),
    ],
    rounds: Annotated[
        int,
        typer.Option("--rounds", "-r", help="How many interview questions"),
    ] = 4,
    voice: Annotated[
        bool,
        typer.Option(
            "--voice",
            "-v",
            help="Speak interviewer text and listen for your answers (pip install -e .[voice])",
        ),
    ] = False,
    speak: Annotated[
        bool,
        typer.Option("--speak", help="Read interviewer replies aloud (TTS)"),
    ] = False,
    listen: Annotated[
        bool,
        typer.Option("--listen", help="Answer using the microphone (STT)"),
    ] = False,
    progress_file: Annotated[Path | None, typer.Option("--progress-file")] = None,
) -> None:
    """Run a multi-turn mock interview (text or optional voice)."""
    do_speak = speak or voice
    do_listen = listen or voice
    voice_io = None
    if do_speak or do_listen:
        from study_helper import voice_io as _voice

        voice_io = _voice

    system = prompts.system_mock_interview(focus, rounds)
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": (
                f"I am the candidate. Domain: {focus.strip()}. "
                f"Begin the mock. Ask question 1 of {rounds} only "
                "(one clear question; no list of multiple questions)."
            ),
        },
    ]
    ppath = _progress_path(progress_file)

    try:
        for i in range(rounds):
            reply = chat(messages)
            messages.append({"role": "assistant", "content": reply})
            console.print(Markdown(reply))
            if do_speak and voice_io is not None:
                voice_io.speak(reply)

            if i == rounds - 1:
                if do_listen and voice_io is not None:
                    console.print("[bold cyan]Your answer (microphone):[/bold cyan]")
                    try:
                        ans_final = voice_io.listen()
                        console.print(f"[dim]Heard:[/dim] {ans_final}")
                    except RuntimeError as err:
                        console.print(f"[yellow]{err}[/yellow]")
                        ans_final = typer.prompt("Type your final answer")
                else:
                    ans_final = typer.prompt("Your answer (final question)")
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"My answer:\n{ans_final}\n\n"
                            "That was my answer to the last question. "
                            "Give your closing scorecard as instructed. "
                            "End with MOCK_INTERVIEW_COMPLETE."
                        ),
                    },
                )
                final = chat(messages)
                messages.append({"role": "assistant", "content": final})
                console.print(Markdown(final))
                if do_speak and voice_io is not None:
                    voice_io.speak(final)
                break

            if do_listen and voice_io is not None:
                console.print("[bold cyan]Your answer (microphone):[/bold cyan]")
                try:
                    ans = voice_io.listen()
                    console.print(f"[dim]Heard:[/dim] {ans}")
                except RuntimeError as err:
                    console.print(f"[yellow]{err}[/yellow]")
                    ans = typer.prompt("Type your answer")
            else:
                ans = typer.prompt("Your answer")
            messages.append({"role": "user", "content": ans})
    except KeyboardInterrupt:
        console.print("\n[dim]Mock interview ended early.[/dim]")
        raise typer.Exit(code=130) from None

    record_interview_session(ppath)
    record_topic(ppath, f"mock-interview:{focus[:60]}")


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
