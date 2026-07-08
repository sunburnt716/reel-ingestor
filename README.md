# Reel Transcriber

Turn Instagram reels you save on your phone into searchable text notes,
automatically. A reel gets shared to an email label, and this tool downloads
its audio with **yt-dlp**, transcribes it locally with **Whisper** (free, no
paid API), and drops a Markdown transcript into a folder of your choice — for
example, an [Obsidian](https://obsidian.md) vault.

```
Phone:  reel -> Copy Link -> Shortcut -> email to a Gmail label   (capture)
This tool:  read Gmail -> yt-dlp -> Whisper -> Markdown transcript  (this repo)
You:  read / synthesize the transcripts however you like            (downstream)
```

Everything runs locally on your machine. The only external service is the
Gmail API (free) used to read the URLs out of a label.

---

## Table of contents

- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Gmail setup (one time)](#gmail-setup-one-time)
- [The capture side (phone shortcut)](#the-capture-side-phone-shortcut)
- [Running it](#running-it)
  - [Level 1: manual](#level-1-manual)
  - [Level 2: scheduled](#level-2-scheduled-windows-task-scheduler)
- [Troubleshooting](#troubleshooting)
- [Caveats](#caveats)

---

## How it works

The tool reads Instagram URLs from a **source**, then for each new one:

1. Downloads the audio track with `yt-dlp`.
2. Transcribes it with a local Whisper model.
3. Writes a Markdown file (with YAML frontmatter) into your output folder.
4. Records what it processed so the same reel is never transcribed twice.

There are two sources, selected by `source` in `config.json`:

- **`gmail`** — reads unread messages under a Gmail label, extracts Instagram
  URLs, and marks each message read once its transcript succeeds. This is the
  automated path.
- **`file`** — reads URLs from a local text/Markdown file (one per line).
  A simple manual fallback that needs no Google setup.

---

## Requirements

- **Python 3.9+**
- **ffmpeg** (both yt-dlp and Whisper need it)
- A **Gmail account** (only if using the `gmail` source)

Python package dependencies are in `requirements.txt` and install via pip.

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/<you>/reel-transcriber.git
cd reel-transcriber

# 2. (Recommended) create a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Install ffmpeg
# Windows (winget):
winget install Gyan.FFmpeg
# macOS (Homebrew):
brew install ffmpeg
# Debian/Ubuntu:
sudo apt install ffmpeg
```

After installing ffmpeg, **open a new terminal** so your PATH picks it up, then
confirm:

```bash
ffmpeg -version
```

> **Windows note:** `winget` installs ffmpeg as a shim that interactive shells
> can see but child processes sometimes cannot. If `yt-dlp` or Whisper later
> reports "ffmpeg not found," set `ffmpeg_location` in your config (see below)
> to the folder containing `ffmpeg.exe`. To find it:
> `dir /s /b "%LOCALAPPDATA%\Microsoft\WinGet\Packages\*ffmpeg.exe"`

---

## Configuration

Copy the example and edit your local copy (never commit the real one):

```bash
# Windows
copy config.example.json config.json
# macOS / Linux
cp config.example.json config.json
```

| field                  | what it is                                                                 |
| ---------------------- | -------------------------------------------------------------------------- |
| `source`               | `"gmail"` (automated) or `"file"` (manual queue)                           |
| `gmail_label`          | exact Gmail label reels arrive under (case-sensitive, e.g. `Reels`)        |
| `queue_file`           | only used when `source` is `"file"` — path to a text/Markdown file of URLs |
| `output_dir`           | folder where transcripts are written                                       |
| `whisper_model`        | `tiny` / `base` / `small` / `medium` / `large` — bigger = slower, better   |
| `cookies_from_browser` | `chrome`, `firefox`, `edge`, or `""` to send none. See caveats.            |
| `ffmpeg_location`      | folder containing `ffmpeg.exe`; leave `""` if ffmpeg is on PATH            |

Paths on Windows use double backslashes in JSON (`C:\\Users\\you\\...`).

`base` is a good default: runs on CPU in seconds per reel, no GPU needed.

---

## Gmail setup (one time)

Skip this if you use `source: "file"`.

1. Go to <https://console.cloud.google.com/> and create a project (free).
2. **APIs & Services -> Library** -> search **Gmail API** -> **Enable**.
   (If you skip this you'll get a `403 accessNotConfigured` error at runtime.)
3. **APIs & Services -> Google Auth Platform** (formerly "OAuth consent
   screen"):
   - **Audience** tab -> User type **External**.
   - Add your own Gmail address under **Test users**.
4. **Credentials -> Create Credentials -> OAuth client ID -> Desktop app.**
   Download the JSON. It should begin with `{ "installed": { ... }`. If it
   begins with `"web"`, you picked the wrong type — recreate as Desktop app.
5. Rename the downloaded file to **`credentials.json`** and place it in the
   project folder (next to `gmail_client.py`).

On first run the tool opens a browser for a one-time consent. You'll see a
"Google hasn't verified this app" screen — this is expected for a personal app;
click **Advanced -> Go to [app] (unsafe) -> Allow**. A `token.json` is cached so
later runs are silent.

> **Important — testing-mode token expiry:** while the app is in "Testing"
> status, Google expires the token about every **7 days**, after which a
> background/scheduled run will hang waiting for a browser consent it can't
> show. To make it truly hands-off, click **Publish app** on the Google Auth
> Platform screen to move it to Production. For a single personal user on their
> own Gmail, accepting the unverified status is fine and it stops the expiry.

### Scope

The tool requests `gmail.modify`. It only reads messages under your chosen
label and removes their **unread** flag after transcribing. It never sends,
deletes, or touches anything outside that label.

---

## The capture side (phone shortcut)

This repo handles ingestion; you still need to get reel URLs into the label.
The reliable pattern on iOS (Instagram's share sheet hands off an image, not a
clean URL, so read from the clipboard instead):

1. Set up a Gmail filter so mail to `youraddress+reels@gmail.com` skips the
   inbox and gets your label. (Gmail treats `+anything` as the same inbox.)
2. Build an iOS Shortcut: **Get Clipboard -> Send Email** (to your `+reels`
   address, compose sheet off).
3. Usage: on a reel tap **Share -> Copy Link**, then run the shortcut (a Back
   Tap gesture or Home Screen icon is fastest).

Any capture method works as long as reel URLs land in the label unread. On
other platforms, adapt freely.

---

## Running it

### Level 1: manual

```bash
python reel_transcriber.py
```

Processes every new URL from the source, skips ones already done (tracked in
`processed.json`), and writes one transcript per reel. Safe to re-run.

### Level 2: scheduled (Windows Task Scheduler)

1. Edit `run_transcriber.bat`: set `PROJECT_DIR` to this folder and `PYTHON` to
   your Python path (`where python`), or to `.venv\Scripts\python.exe` if you
   used a venv. **Use the same Python you installed the packages into** — a
   mismatch here is the most common setup failure.
2. **Task Scheduler -> Create Task** (not "Basic Task"):
   - **General:** name it; check **Run whether user is logged on or not**.
   - **Triggers:** New -> On a schedule -> Daily, repeat every 1 hour.
   - **Settings:** check **Run task as soon as possible after a scheduled start
     is missed** (this catches up after the machine was asleep).
   - **Actions:** New -> Start a program -> browse to `run_transcriber.bat`.
3. Save (enter your Windows password if prompted).

> A repeating task shows a persistent **"Running"** status for its whole
> schedule window — that's normal, not a hang. The script itself fires briefly
> each interval. Trust `reel_transcriber.log`, not the status label.

**Does it run while the machine is asleep?** No, not reliably — Task Scheduler
doesn't run during sleep and the "wake to run" option is flaky on laptops. The
"run after a missed start" setting above makes it catch up when the machine is
next awake, which is fine for non-urgent content.

---

## Troubleshooting

| symptom                                                            | cause & fix                                                                                                                                                                            |
| ------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `No new URLs found`                                                | Label name mismatch (case-sensitive!) or messages already read. Search `label:YourLabel is:unread` in Gmail to see exactly what the tool sees.                                         |
| `ModuleNotFoundError` / "libraries not found"                      | pip installed into a different Python than the one running the script. Run `<your-python> -m pip install -r requirements.txt` with the _exact_ interpreter you launch the script with. |
| `403 accessNotConfigured`                                          | Gmail API not enabled for the project. Enable it and wait a few minutes.                                                                                                               |
| `403 access_denied`                                                | Your Gmail isn't a Test user, or app is Internal. Add yourself under Audience -> Test users.                                                                                           |
| `Could not copy Chrome cookie database`                            | Chrome locks its cookie DB while open. Close Chrome, use `firefox`, or set `cookies_from_browser: ""`.                                                                                 |
| `ffprobe and ffmpeg not found` / `WinError 2` during transcription | ffmpeg not visible to the subprocess. Set `ffmpeg_location` to the folder holding `ffmpeg.exe`.                                                                                        |
| Scheduled task hangs on "Running" and never logs progress          | Token expired and it's silently waiting for a browser consent. Run once manually to refresh `token.json`, then **Publish app** to stop the weekly expiry.                              |

The log at `reel_transcriber.log` records every run with timestamps and is the
source of truth for what actually happened.

---

## Caveats

- **Instagram + yt-dlp is finicky.** Public reels usually download without
  cookies. Some need `cookies_from_browser` set to a browser you're logged into
  Instagram on. Private or removed reels won't download at all.
- **Audio only.** This captures spoken content. On-screen text that's never
  spoken aloud is not transcribed.
- **First run downloads the Whisper model** (~140 MB for `base`), once.
- **Local compute.** A ~60-second reel on `base` transcribes in roughly
  10-30 seconds on CPU.

---

## Project layout

```
reel-transcriber/
├── reel_transcriber.py     # main script
├── gmail_client.py          # Gmail API reader (used when source = gmail)
├── config.example.json      # copy to config.json and edit
├── requirements.txt
├── run_transcriber.bat      # Task Scheduler wrapper (Windows, Level 2)
├── .gitignore
└── README.md
```

`config.json`, `credentials.json`, `token.json`, `processed.json`, and the log
are gitignored. **Never commit `credentials.json` or `token.json`** — they are
live secrets.

## License

MIT (or your choice). yt-dlp, Whisper, and the Google client libraries retain
their own licenses.
