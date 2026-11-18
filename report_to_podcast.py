#!/usr/bin/env python3
"""Turn a written market report into a two-voice podcast episode, with local text-to-speech.

Two stages, so the script can be read and edited before any audio is made:

  script  report.md -> episode.txt   (Claude writes a dialogue grounded only in the report)
  audio   episode.txt -> episode.mp3 (Kokoro, a local TTS model; nothing leaves the machine)
  make    both in one go

Examples:
  python report_to_podcast.py make  ../space-market-intel/market-studies/reaction-wheel/2026-09-30/report.md
  python report_to_podcast.py script report.md --minutes 10 -o rw.txt
  python report_to_podcast.py audio rw.txt -o rw.mp3

The script stage needs Anthropic credentials (ANTHROPIC_API_KEY, or `ant auth login`).
The audio stage needs none: it runs Kokoro on the CPU and ffmpeg for the MP3.

Episode format (episode.txt) is plain text, one turn per paragraph:

  ALEX: Welcome back...
  SAM: Thanks. The headline is...

Lines starting with '#' are comments and are not spoken. Edit freely before running `audio`.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

MODEL = "claude-opus-5-5"
WORDS_PER_MINUTE = 210  # at the default --speed 1.5; --minutes means listening time
SPEAKERS = ("ALEX", "SAM")
DEFAULT_VOICES = {"ALEX": "am_michael", "SAM": "af_heart"}  # Kokoro American English voices
SAMPLE_RATE = 24000  # Kokoro's output rate

COMMON_RULES = """\
You turn a written market-intelligence report into the script for a two-person audio episode.

The speakers:
- ALEX hosts. Asks what a smart listener from outside the niche would ask, reacts, pushes for the
  "so what", and summarises.
- SAM has read the report closely and explains what it found.

Accuracy is the point of this episode. The listener will act on it, and cannot see the page.

Two kinds of content are allowed, and they are kept apart.

1. MARKET FACTS come only from the report (and any correction note or extra note you are given).
   Every company, product, number, date, contract, failure, judgment and comparison must be in that
   text. If the report does not say it, the speakers do not say it.
   - Keep the report's evidence labels. Where it marks a claim flight-proven or roadmap (announced,
     qualified but not flown, vendor-claimed, unconfirmed), say which whenever that claim comes up.
     "Qualified, not flown" must not become "proven".
   - Keep the report's hedges. A vendor's own description stays attributed to the vendor. Do not
     upgrade a claim or soften a caveat or correction.
   - Treat the report as a snapshot as of its compile date, not as live news.
   - If you are given a correction note, do not repeat a claim it says is withdrawn or superseded.
   - Neutral register: no ranking beyond the report's, no sales language, no buy/avoid advice.

2. BACKGROUND may come from general engineering knowledge, to explain a concept the report relies on:
   how the hardware works, what a term means (momentum, torque, TRL, qualification), why a property
   matters to a spacecraft. Rules for background:
   - It explains concepts only. It never names a company, product, programme or mission, never gives
     a market figure, price, date or count, and never says anything about who leads or what is new.
   - Only settled textbook knowledge. If you are not sure it is true, leave it out.
   - Put a line containing exactly "# background" immediately above every turn that contains
     background. Such a turn may still mention report facts, but nothing else outside the report.
   - Keep background to about a fifth of the episode at most. It serves the findings; it is not a
     lecture.

Make it sound like speech:
- Spell out units and symbols as spoken: "newton-metre-seconds" not "N·m·s", "3 sigma" not "3σ",
  "arc-seconds" not "″", "watt-hours per kilogram" not "Wh/kg", "about" not "~". Numbers stay digits.
- No markdown, bullets, headings, file paths, commit hashes or section numbers. No table read-outs.
- Short turns, natural back-and-forth.

Output only the script: one turn per paragraph, each starting with "ALEX:" or "SAM:", plus the
"# background" marker lines. Nothing else.
"""

STYLE_PROMPTS = {
    "story": """\
Style: a story-led episode, lively but not breezy.
- Cold open: ALEX starts with the single most surprising or consequential finding, as a question
  or a tension, before saying what the report is. Then one line on what the report is and its date.
- Build the episode around three to five stories the report supports: a tension, an upset, a
  puzzle, a cautionary tale, something that has been "coming soon" for years. Tell each one with a
  beginning, a turn and a consequence, and end it on why it matters, in the report's own terms.
- About three numbers per story. Choose the ones that carry the point; drop the rest.
- ALEX is curious and a little sceptical: reacts ("hang on, so the best spec on paper hasn't
  flown?"), pushes back, asks what it means for someone buying. SAM answers with the evidence and
  says plainly where the report says the evidence runs out.
- Warmth and light humour are fine, aimed at situations, never at a company or person, and never at
  the cost of a hedge.
- Close with a short recap of the stories, and the date they are as of.
""",
    "briefing": """\
Style: a straight briefing.
- Open by saying what the report is and its compile date.
- Walk the main findings in order of importance, with the few figures that carry each one.
- Plain, efficient turns; little background.
- End with a recap of the main findings and the date they are as of.
""",
}


# --------------------------------------------------------------------------- script stage

def find_index_note(report: Path) -> str | None:
    """For market-studies/<category>/<date>/report.md, return that study's row from index.md.

    The index row is where a correction to a frozen study is recorded (a warning sign marks the
    claims not to reuse), so the script writer needs to see it alongside the report.
    """
    date_dir, cat_dir = report.parent, report.parent.parent
    index = cat_dir.parent / "index.md"
    if not index.is_file():
        return None
    for line in index.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0] == cat_dir.name and cells[1] == date_dir.name:
            return line
    return None


def write_script(report: Path, minutes: int, notes: list[str], effort: str, style: str) -> str:
    import anthropic

    text = report.read_text(encoding="utf-8")
    target_words = minutes * WORDS_PER_MINUTE

    parts = [f"<report path=\"{report.name}\">\n{text}\n</report>"]
    index_note = find_index_note(report)
    if index_note:
        parts.append(
            "<correction_note source=\"the library's index row for this report\">\n"
            f"{index_note}\n</correction_note>"
        )
    for n in notes:
        parts.append(f"<note>\n{n}\n</note>")
    parts.append(
        f"Write the episode script. Aim for about {target_words} words "
        f"(roughly {minutes} minutes spoken)."
    )

    client = anthropic.Anthropic()
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=32000,
        system=COMMON_RULES + "\n" + STYLE_PROMPTS[style],
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        # On a policy decline, the API retries on a fallback model inside the same call.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": "\n\n".join(parts)}],
    ) as stream:
        for _ in stream.text_stream:
            print(".", end="", file=sys.stderr, flush=True)
        message = stream.get_final_message()
    print(file=sys.stderr)

    if message.stop_reason == "refusal":
        sys.exit("The model declined to write this script (stop_reason=refusal).")
    if message.stop_reason == "max_tokens":
        sys.exit("The script was cut off at max_tokens; try a shorter --minutes.")

    script = "".join(b.text for b in message.content if b.type == "text").strip()
    header = (
        f"# Source: {report}\n"
        f"# Generated by {message.model}. Check it against the report before you rely on it.\n"
    )
    return header + "\n" + script + "\n"


NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*")


def split_background(script: str) -> tuple[str, str]:
    """Split a script into (report-sourced turns, background turns) by the '# background' marker."""
    sourced, background = [], []
    for para in re.split(r"\n\s*\n", script):
        lines = para.strip().splitlines()
        is_bg = any(l.strip().lower() == "# background" for l in lines)
        spoken = "\n".join(l for l in lines if not l.lstrip().startswith("#"))
        if spoken:
            (background if is_bg else sourced).append(spoken)
    return "\n\n".join(sourced), "\n\n".join(background)


def unsupported_numbers(spoken: str, source: str) -> list[str]:
    """Numbers in spoken text that never appear in the source text.

    A cheap tripwire for invented figures. It cannot catch a real number attached to the wrong
    product, so it does not replace reading the script; it only points at where to look first.
    """
    source_nums = {n.replace(",", "") for n in NUMBER.findall(source)}
    missing = []
    for n in NUMBER.findall(spoken):
        n = n.replace(",", "")
        if n not in source_nums and n not in missing:
            missing.append(n)
    return missing


def check_script(script: str, report: Path) -> None:
    source = report.read_text(encoding="utf-8")
    note = find_index_note(report)
    if note:
        source += "\n" + note
    sourced, background = split_background(script)
    missing = unsupported_numbers(sourced, source)
    if missing:
        print("WARNING: these numbers are in the script but not in the report — check them: "
              + ", ".join(missing), file=sys.stderr)
    else:
        print("Number check: every number in the report-sourced turns appears in the report.",
              file=sys.stderr)
    total = len(sourced.split()) + len(background.split())
    if background:
        share = len(background.split()) / total
        print(f"Background: {share:.0%} of spoken words are marked '# background' "
              "(general knowledge, not from the report).", file=sys.stderr)
        if share > 0.3:
            print("WARNING: background is over 30% of the episode.", file=sys.stderr)
        bg_nums = [n for n in NUMBER.findall(background)]
        if bg_nums:
            print("NOTE: background turns contain numbers — check they are textbook, not market "
                  "figures: " + ", ".join(dict.fromkeys(bg_nums)), file=sys.stderr)


# --------------------------------------------------------------------------- audio stage

def parse_episode(text: str) -> list[tuple[str, str]]:
    turns: list[tuple[str, str]] = []
    for para in re.split(r"\n\s*\n", text):
        lines = [l for l in para.strip().splitlines() if not l.lstrip().startswith("#")]
        if not lines:
            continue
        para = " ".join(l.strip() for l in lines)
        m = re.match(r"^\**([A-Z][A-Z ]*?)\**\s*:\s*(.+)$", para)
        if not m:
            if turns:  # continuation of the previous speaker
                spk, prev = turns[-1]
                turns[-1] = (spk, prev + " " + para)
            continue
        turns.append((m.group(1).strip(), m.group(2).strip()))
    return turns


# Safety net for symbols that slip through the script stage; Kokoro reads these badly or not at all.
SPOKEN = [
    (r"N·m·s|N\.m\.s|Nms\b", "newton-metre-seconds"),
    (r"mN·m|mNm\b", "milli-newton-metres"),
    (r"N·m\b|Nm\b", "newton-metres"),
    (r"(\d)\s*σ", r"\1 sigma"),
    (r"σ", "sigma"),
    (r"(\d)\s*″", r"\1 arc-seconds"),
    (r"\barcsec\b", "arc-seconds"),
    (r"Wh/kg", "watt-hours per kilogram"),
    (r"W/kg", "watts per kilogram"),
    (r"(\d)\s*kWh\b", r"\1 kilowatt-hours"),
    (r"(\d)\s*Wh\b", r"\1 watt-hours"),
    (r"(\d)\s*kW\b", r"\1 kilowatts"),
    (r"(\d)\s*kg\b", r"\1 kilograms"),
    (r"(\d)\s*g\b", r"\1 grams"),
    (r"(\d)\s*°", r"\1 degrees"),
    (r"~\s*", "about "),
    (r"≈\s*", "about "),
    (r"≥\s*", "at least "),
    (r"≤\s*", "at most "),
    (r"[–—]", ", "),
    (r"[*_`#]", ""),
]


def speakable(text: str) -> str:
    for pat, rep in SPOKEN:
        text = re.sub(pat, rep, text)
    return text


def make_audio(episode: str, out: Path, voices: dict[str, str], speed: float) -> float:
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline

    turns = parse_episode(episode)
    if not turns:
        sys.exit("No speaker turns found. Each paragraph should start with 'ALEX:' or 'SAM:'.")
    unknown = sorted({s for s, _ in turns} - set(voices))
    if unknown:
        # Give extra speakers the leftover default voices rather than failing.
        spare = [v for v in ("bm_george", "bf_emma", "am_adam", "af_bella") if v not in voices.values()]
        for s in unknown:
            voices[s] = spare.pop(0) if spare else next(iter(voices.values()))

    pipeline = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
    gap = np.zeros(int(SAMPLE_RATE * 0.35 / speed), dtype=np.float32)
    pieces = []
    for i, (spk, text) in enumerate(turns, 1):
        print(f"  [{i}/{len(turns)}] {spk}", file=sys.stderr)
        for _, _, audio in pipeline(speakable(text), voice=voices[spk], speed=speed):
            pieces.append(np.asarray(audio, dtype=np.float32))
        pieces.append(gap)
    audio = np.concatenate(pieces)

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() == ".wav":
        sf.write(out, audio, SAMPLE_RATE)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "episode.wav"
            sf.write(wav, audio, SAMPLE_RATE)
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav),
                 "-codec:a", "libmp3lame", "-q:a", "4", str(out)],
                check=True,
            )
    return len(audio) / SAMPLE_RATE


# --------------------------------------------------------------------------- CLI

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def script_args(p):
        p.add_argument("report", type=Path, help="the markdown report to read")
        p.add_argument("--minutes", type=int, default=12, help="target episode length (default 12)")
        p.add_argument("--note", action="append", default=[],
                       help="extra instruction for the script writer, e.g. a correction (repeatable)")
        p.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
        p.add_argument("--style", default="story", choices=sorted(STYLE_PROMPTS),
                       help="story (default): built around a few stories; briefing: straight read-out")

    def audio_args(p):
        p.add_argument("--voice", action="append", default=[], metavar="SPEAKER=VOICE",
                       help=f"override a voice, e.g. ALEX=bm_george (defaults: {DEFAULT_VOICES})")
        p.add_argument("--speed", type=float, default=1.5,
                       help="speaking rate; 1.0 is Kokoro's natural pace (default 1.5)")

    p = sub.add_parser("script", help="report.md -> episode.txt")
    script_args(p)
    p.add_argument("-o", "--out", type=Path)

    p = sub.add_parser("audio", help="episode.txt -> episode.mp3")
    p.add_argument("episode", type=Path)
    p.add_argument("-o", "--out", type=Path)
    p.add_argument("--report", type=Path, help="re-run the number check against this report first")
    audio_args(p)

    p = sub.add_parser("make", help="report.md -> episode.txt + episode.mp3")
    script_args(p)
    p.add_argument("-o", "--out", type=Path, help="output .mp3 (the .txt is written beside it)")
    audio_args(p)

    args = ap.parse_args()

    def default_stem(report: Path) -> Path:
        # market-studies/reaction-wheel/2026-09-30/report.md -> episodes/reaction-wheel-2026-09-30
        stem = "-".join(report.resolve().parts[-3:-1]) if report.stem == "report" else report.stem
        return Path("episodes") / stem

    if args.cmd in ("script", "make"):
        if not args.report.is_file():
            sys.exit(f"No such report: {args.report}")
        out_txt = (args.out.with_suffix(".txt") if args.out
                   else default_stem(args.report).with_suffix(".txt"))
        print(f"Writing script for {args.report} ...", file=sys.stderr)
        script = write_script(args.report, args.minutes, args.note, args.effort, args.style)
        out_txt.parent.mkdir(parents=True, exist_ok=True)
        out_txt.write_text(script, encoding="utf-8")
        print(f"Script: {out_txt} ({len(script.split())} words)", file=sys.stderr)
        check_script(script, args.report)
        if args.cmd == "script":
            return
        episode_path, report = out_txt, args.report
    else:
        episode_path, report = args.episode, args.report
        if report:
            check_script(episode_path.read_text(encoding="utf-8"), report)

    voices = dict(DEFAULT_VOICES)
    for v in args.voice:
        spk, _, name = v.partition("=")
        voices[spk.strip().upper()] = name.strip()
    out_audio = args.out.with_suffix(args.out.suffix or ".mp3") if args.out and args.cmd == "audio" \
        else (args.out if args.out else episode_path.with_suffix(".mp3"))
    print(f"Synthesising {episode_path} ...", file=sys.stderr)
    secs = make_audio(episode_path.read_text(encoding="utf-8"), out_audio, voices, args.speed)
    print(f"Audio: {out_audio} ({secs / 60:.1f} min)", file=sys.stderr)


if __name__ == "__main__":
    main()
