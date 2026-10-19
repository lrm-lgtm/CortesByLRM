"""Funções puras para planejar cortes e produzir legendas e comando FFmpeg."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class Cue:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class Suggestion:
    start: float
    end: float
    score: float
    preview: str


def check_rights(basis: str, evidence: str) -> None:
    """Um rótulo de direitos não substitui verificar a autorização."""
    allowed = {"proprio", "licenciado", "campanha"}
    if basis not in allowed:
        raise ValueError("Direitos devem ser: proprio, licenciado ou campanha.")
    if not evidence or not evidence.strip():
        raise ValueError("Informe evidência verificável de titularidade/autorização.")


def _seconds(value: str) -> float:
    match = re.fullmatch(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})", value.strip())
    if not match:
        raise ValueError("Timestamp SRT inválido: " + value)
    h, m, s, milli = map(int, match.groups())
    if m >= 60 or s >= 60:
        raise ValueError("Timestamp SRT fora dos limites: " + value)
    return h * 3600 + m * 60 + s + milli / 1000


def parse_srt(raw: str) -> list[Cue]:
    """Aceita SRT com CRLF e quebra de linha simples; ignora bloco inválido."""
    raw = raw.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    cues: list[Cue] = []
    for block in re.split(r"\n\s*\n", raw):
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        stamp = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if stamp is None or stamp == len(lines) - 1:
            continue
        ends = lines[stamp].split("-->")
        if len(ends) != 2:
            continue
        try:
            start, end = _seconds(ends[0]), _seconds(ends[1])
        except ValueError:
            continue
        content = re.sub(r"<[^>]*>", "", " ".join(lines[stamp + 1:])).strip()
        if end <= start or not content:
            continue
        cues.append(Cue(start, end, content))
    cues.sort(key=lambda cue: (cue.start, cue.end))
    return cues


def suggest_cuts(
    cues: list[Cue], limit: int = 5, min_seconds: float = 15.0,
    max_seconds: float = 60.0, target_seconds: float = 38.0,
) -> list[Suggestion]:
    """Sugestões heurísticas. Nunca equivalem a previsão de viralização."""
    if limit < 1 or min_seconds <= 0 or max_seconds < min_seconds:
        raise ValueError("Parâmetros de duração inválidos.")
    found: list[Suggestion] = []
    for i, first in enumerate(cues):
        words: list[str] = []
        for last in cues[i:]:
            if last.end - first.start > max_seconds + 0.001:
                break
            words.append(last.text)
            span = last.end - first.start
            if span < min_seconds:
                continue
            content = " ".join(words)
            word_count = len(content.split())
            if word_count < 10:
                continue
            hook = first.text.lower()
            hooks = ("por que", "como ", "você sabia", "o erro", "imagine", "nunca", "segredo", "mas ")
            score = 100 - abs(span - target_seconds) * 1.2
            score += min(word_count, 100) * 0.12
            score += 9 if any(x in hook for x in hooks) else 0
            score += 4 if "?" in first.text or "!" in first.text else 0
            score += 3 if last.text.endswith((".", "!", "?")) else 0
            found.append(Suggestion(round(first.start, 3), round(last.end, 3), round(score, 2), content[:180]))
    found.sort(key=lambda x: (-x.score, x.start))
    chosen: list[Suggestion] = []
    for clip in found:
        # Evita que um mesmo trecho domine todas as sugestões.
        if any(max(0, min(clip.end, old.end) - max(clip.start, old.start)) /
               min(clip.end-clip.start, old.end-old.start) > 0.55 for old in chosen):
            continue
        chosen.append(clip)
        if len(chosen) >= limit:
            break
    return chosen


def _srt_time(seconds: float) -> str:
    millis = max(0, int(round(seconds * 1000)))
    h, rest = divmod(millis, 3_600_000)
    m, rest = divmod(rest, 60_000)
    s, ms = divmod(rest, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def clip_srt(cues: list[Cue], start: float, end: float) -> str:
    """Gera SRT com timestamps relativos ao novo vídeo."""
    if end <= start:
        raise ValueError("Trecho precisa ter duração positiva.")
    result = []
    count = 0
    for cue in cues:
        left = max(cue.start, start)
        right = min(cue.end, end)
        if right <= left:
            continue
        count += 1
        result.append(
            f"{count}\n{_srt_time(left-start)} --> {_srt_time(right-start)}\n{cue.text}\n"
        )
    return "\n".join(result)


def ffmpeg_command(video: Path, output: Path, start: float, end: float) -> list[str]:
    """Gera MP4 9:16 com letterbox, sem cortar indevidamente o sujeito.

    Legendas são geradas em SRT separado; burn-in é uma P1.
    """
    if end <= start or start < 0:
        raise ValueError("Intervalo de vídeo inválido.")
    return [
        "ffmpeg", "-hide_banner", "-nostdin", "-y",
        "-i", str(video), "-ss", f"{start:.3f}", "-t", f"{end-start:.3f}",
        "-map", "0:v:0", "-map", "0:a?",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,"
               "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-movflags", "+faststart", str(output),
    ]


def serialize_suggestions(suggestions: list[Suggestion]) -> list[dict]:
    return [asdict(x) for x in suggestions]
