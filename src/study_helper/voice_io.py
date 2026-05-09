"""Optional voice I/O (install: pip install -e '.[voice]')."""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import speech_recognition as sr


def _plain_for_speech(text: str, max_len: int = 8000) -> str:
    t = re.sub(r"```[^`]*```", " code block omitted. ", text, flags=re.DOTALL)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = re.sub(r"[#*_>\[\]()]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:max_len]


def speak(text: str) -> None:
    try:
        import pyttsx3
    except ImportError as e:
        msg = "Voice output needs optional deps: pip install -e '.[voice]'"
        raise RuntimeError(msg) from e
    engine = pyttsx3.init()
    try:
        engine.setProperty("rate", 185)
    except Exception:
        pass
    utter = _plain_for_speech(text)
    if utter:
        engine.say(utter)
        engine.runAndWait()


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str) -> int | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _configure_recognizer() -> "sr.Recognizer":
    import speech_recognition as sr

    r = sr.Recognizer()
    r.pause_threshold = _env_float("STUDY_HELPER_MIC_PAUSE_SEC", 1.0)
    r.dynamic_energy_threshold = not _truthy("STUDY_HELPER_MIC_FIXED_THRESHOLD")
    return r


def _prepare_source(
    r: "sr.Recognizer",
    source: "sr.Microphone",
    noise_sec: float,
    energy_override: int | None,
) -> None:
    if noise_sec > 0:
        r.adjust_for_ambient_noise(source, duration=min(noise_sec, 2.0))
    if energy_override is not None:
        r.energy_threshold = energy_override
    elif _truthy("STUDY_HELPER_MIC_SENSITIVE"):
        r.energy_threshold = max(50, int(r.energy_threshold * 0.6))


def listen(
    phrase_time_limit: int = 120,
    timeout: int = 45,
    max_attempts: int = 3,
) -> str:
    try:
        import speech_recognition as sr
    except ImportError as e:
        msg = "Voice input needs optional deps: pip install -e '.[voice]' (PyAudio required for microphone)"
        raise RuntimeError(msg) from e
    lang = os.environ.get("STUDY_HELPER_SPEECH_LANG", "en-US").strip() or "en-US"
    noise_sec = _env_float("STUDY_HELPER_MIC_NOISE_ADJUST_SEC", 1.0)
    if _truthy("STUDY_HELPER_MIC_SKIP_NOISE_ADJUST"):
        noise_sec = 0.0
    energy_override = _env_int("STUDY_HELPER_MIC_ENERGY")

    try:
        mic = sr.Microphone()
    except OSError as e:
        msg = "No microphone found or PyAudio not installed correctly."
        raise RuntimeError(msg) from e

    last_err: Exception | None = None
    heard_any_audio = False
    for _ in range(max_attempts):
        r = _configure_recognizer()
        with mic as source:
            _prepare_source(r, source, noise_sec, energy_override)
            try:
                audio = r.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
            except sr.WaitTimeoutError as e:
                last_err = e
                continue
            heard_any_audio = True
        try:
            return r.recognize_google(audio, language=lang)
        except sr.UnknownValueError as e:
            last_err = e
            continue
        except sr.RequestError as e:
            msg = (
                "Speech recognition service error (network or quota). "
                f"Details: {e!s}. Check internet or type your answer."
            )
            raise RuntimeError(msg) from e

    if not heard_any_audio:
        msg = (
            "No speech captured in time (mic too quiet, wrong device, or you started too late). "
            "Try: set the correct default microphone in Windows, speak right after adjusting for noise, "
            "or set STUDY_HELPER_MIC_SENSITIVE=1."
        )
        raise RuntimeError(msg) from last_err

    detail = (
        "Google could not turn the audio into text (noise, mumbling, or wrong language). "
        "Try: quieter room, speak clearly, set STUDY_HELPER_SPEECH_LANG=en-US or en-IN, "
        "STUDY_HELPER_MIC_SENSITIVE=1, or STUDY_HELPER_MIC_SKIP_NOISE_ADJUST=1."
    )
    raise RuntimeError(detail) from last_err
