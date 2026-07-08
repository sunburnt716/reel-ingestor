#!/usr/bin/env python3
"""
reel_transcriber.py
-------------------
Takes Instagram reel URLs from a source (a Gmail label, or a local queue file),
downloads the audio with yt-dlp, transcribes it locally with Whisper (free, no
API), and writes a Markdown transcript into the Obsidian vault's raw-sources
folder. Handled reels are marked read in Gmail so they aren't reprocessed.

Level 1: run manually  ->  python reel_transcriber.py
Level 2: run on a schedule via Windows Task Scheduler (see README).

Everything runs locally. No paid APIs. No account required.
"""

import json
import logging
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

# --------------------------------------------------------------------------
# Config loading
# --------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "config.json"
STATE_PATH = SCRIPT_DIR / "processed.json"
LOG_PATH = SCRIPT_DIR / "reel_transcriber.log"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        sys.exit(
            f"Missing config.json. Copy config.example.json to config.json "
            f"and fill in your paths.\nExpected at: {CONFIG_PATH}"
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_state() -> dict:
    if STATE_PATH.exists():
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"processed": {}}


def save_state(state: dict) -> None:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def extract_shortcode(url: str) -> str | None:
    """Pull the reel/post shortcode out of an Instagram URL for naming + dedup."""
    m = re.search(r"instagram\.com/(?:reel|reels|p)/([A-Za-z0-9_-]+)", url)
    return m.group(1) if m else None


def read_queue(queue_path: Path) -> list[str]:
    """Read URLs from the queue file, ignoring blank lines, comments, and markdown."""
    if not queue_path.exists():
        logging.warning("Queue file not found: %s", queue_path)
        return []
    urls = []
    for line in queue_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("<!--"):
            continue
        # Grab any instagram URL found on the line (handles markdown/pasted text)
        m = re.search(r"https?://\S*instagram\.com/\S+", line)
        if m:
            urls.append(m.group(0).rstrip(">)],."))
    return urls


# --------------------------------------------------------------------------
# Core steps
# --------------------------------------------------------------------------

def download_audio(
    url: str,
    workdir: Path,
    cookies_from_browser: str | None,
    ffmpeg_location: str | None,
) -> Path | None:
    """Use yt-dlp to grab the audio track only. Returns path to the audio file."""
    out_template = str(workdir / "%(id)s.%(ext)s")
    cmd = [
        "yt-dlp",
        "-f", "bestaudio/best",
        "--extract-audio",
        "--audio-format", "mp3",
        "-o", out_template,
        "--no-playlist",
        "--quiet",
        "--no-warnings",
    ]
    # Point yt-dlp straight at ffmpeg so it doesn't depend on PATH (important
    # on Windows where winget installs it as a shim that subprocesses can't see).
    if ffmpeg_location:
        cmd += ["--ffmpeg-location", ffmpeg_location]
    # Instagram often needs login cookies for full/public content.
    if cookies_from_browser:
        cmd += ["--cookies-from-browser", cookies_from_browser]
    cmd.append(url)

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError:
        sys.exit("yt-dlp not found. Install it: pip install yt-dlp")
    except subprocess.CalledProcessError as e:
        logging.error("yt-dlp failed for %s\n%s", url, e.stderr.strip())
        return None

    mp3s = list(workdir.glob("*.mp3"))
    return mp3s[0] if mp3s else None


def transcribe(audio_path: Path, model_size: str):
    """Transcribe with local Whisper. Returns (text, detected_language)."""
    try:
        import whisper  # openai-whisper
    except ImportError:
        sys.exit("Whisper not found. Install it: pip install -U openai-whisper")

    logging.info("Loading Whisper model '%s' (first run downloads it once)...", model_size)
    model = whisper.load_model(model_size)
    result = model.transcribe(str(audio_path), fp16=False)
    return result["text"].strip(), result.get("language", "unknown")


def write_transcript(
    output_dir: Path, url: str, shortcode: str, text: str, language: str
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    filename = f"{today} - reel-{shortcode}.md"
    path = output_dir / filename

    frontmatter = (
        "---\n"
        f"source: Instagram Reel\n"
        f"url: {url}\n"
        f"type: video\n"
        f"date_added: {today}\n"
        f"status: unprocessed\n"
        f"language: {language}\n"
        f"tags: [reel, transcript]\n"
        "---\n\n"
    )
    body = (
        f"# Reel Transcript ({shortcode})\n\n"
        f"> Auto-transcribed with local Whisper. Original: {url}\n\n"
        "## Transcript\n\n"
        f"{text}\n"
    )
    path.write_text(frontmatter + body, encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> None:
    setup_logging()
    config = load_config()
    state = load_state()

    output_dir = Path(config["output_dir"])
    model_size = config.get("whisper_model", "base")
    cookies_from_browser = config.get("cookies_from_browser") or None
    ffmpeg_location = config.get("ffmpeg_location") or None
    source = config.get("source", "file").lower()

    # Put ffmpeg on PATH for THIS process so Whisper (which shells out to
    # ffmpeg internally and ignores our --ffmpeg-location flag) can find it too.
    if ffmpeg_location:
        import os
        os.environ["PATH"] = ffmpeg_location + os.pathsep + os.environ.get("PATH", "")

    # --- Gather work items: each is {"url", "message_id" (or None)} ---
    if source == "gmail":
        import gmail_client
        label = config.get("gmail_label", "Reels")
        logging.info("Reading reel URLs from Gmail label '%s'...", label)
        items = gmail_client.get_reel_urls(label)
    else:
        queue_path = Path(config["queue_file"])
        logging.info("Reading reel URLs from queue file: %s", queue_path)
        items = [{"url": u, "message_id": None} for u in read_queue(queue_path)]

    if not items:
        logging.info("No new URLs found. Nothing to do.")
        return

    logging.info("Found %d URL(s) to consider.", len(items))
    new_count = 0

    for item in items:
        url = item["url"]
        message_id = item.get("message_id")
        shortcode = extract_shortcode(url)
        if not shortcode:
            logging.warning("Could not parse shortcode, skipping: %s", url)
            continue
        if shortcode in state["processed"]:
            logging.info("Already processed, skipping: %s", shortcode)
            # Still clear it from Gmail so it stops showing as unread.
            if source == "gmail" and message_id:
                _safe_mark_read(message_id)
            continue

        logging.info("Processing reel %s ...", shortcode)
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            audio = download_audio(url, workdir, cookies_from_browser, ffmpeg_location)
            if not audio:
                logging.error("Skipping %s (download failed).", shortcode)
                continue
            try:
                text, language = transcribe(audio, model_size)
            except Exception as e:  # noqa: BLE001
                logging.error("Transcription failed for %s: %s", shortcode, e)
                continue

        out_path = write_transcript(output_dir, url, shortcode, text, language)
        state["processed"][shortcode] = {
            "url": url,
            "transcribed_at": datetime.now().isoformat(timespec="seconds"),
            "output": str(out_path),
        }
        save_state(state)

        # Only mark the email read AFTER a successful transcript, so a failure
        # leaves it unread to retry next run.
        if source == "gmail" and message_id:
            _safe_mark_read(message_id)

        new_count += 1
        logging.info("Wrote transcript -> %s", out_path.name)

    logging.info("Done. %d new transcript(s) created.", new_count)


def _safe_mark_read(message_id: str) -> None:
    """Mark a Gmail message read, logging but not crashing on failure."""
    try:
        import gmail_client
        gmail_client.mark_read(message_id)
    except Exception as e:  # noqa: BLE001
        logging.warning("Could not mark message %s read: %s", message_id, e)


if __name__ == "__main__":
    main()