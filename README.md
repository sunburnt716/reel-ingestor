# Reel Transcriber

A small, free, local tool that turns saved Instagram reels into text transcripts
inside an Obsidian vault. It downloads a reel's audio with **yt-dlp** and
transcribes it with **local Whisper** (no paid API, no account). Transcripts land
in the vault's raw-sources folder, ready to be synthesized into notes.

```
Phone: reel -> Copy Link -> Shortcut -> Gmail "Reels" label   (capture)
This script: read Gmail -> yt-dlp -> Whisper -> transcript      (this repo)
Claude: read transcripts -> synthesize into digests            (in Obsidian)
```

The script can read URLs from two sources, set by `source` in config.json:

- `"gmail"` — reads unread mail in your Reels label, marks them read when done
  (fully automated, recommended)
- `"file"` — reads a local text/markdown queue file (simple fallback, manual)

## Requirements

- Python 3.9+
- **ffmpeg** on your PATH (yt-dlp and Whisper both need it)
- Everything else installs via pip

Install ffmpeg on Windows (easiest): `winget install Gyan.FFmpeg`
Then close and reopen your terminal so PATH updates.

## Setup

```bash
# 1. Clone / open the project, then create a virtual env (recommended)
python -m venv .venv
.venv\Scripts\activate          # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create your local config from the example
copy config.example.json config.json     # Windows
#   then edit config.json — see below
```

### config.json fields

| field                  | what it is                                                       |
| ---------------------- | ---------------------------------------------------------------- |
| `source`               | `"gmail"` (automated) or `"file"` (manual queue)                 |
| `gmail_label`          | the Gmail label reels arrive under (e.g. `Reels`)                |
| `queue_file`           | only used when `source` is `"file"`                              |
| `output_dir`           | folder where transcripts are written (your vault videos folder)  |
| `whisper_model`        | `tiny` / `base` / `small` / `medium` / `large` — bigger = slower |
| `cookies_from_browser` | `chrome`, `firefox`, etc. Instagram often needs login cookies.   |

`base` is a good default: fast on CPU, decent accuracy. Bump to `small` if
transcripts are sloppy. You do **not** need a GPU for reel-length clips.

## Gmail setup (one time, free)

To let the script read your Reels label, you create free OAuth credentials:

1. Go to <https://console.cloud.google.com/> and create a new project
   (any name). It's free; no billing needed for this.
2. In the project, open **APIs & Services -> Library**, search **Gmail API**,
   and click **Enable**.
3. Go to **APIs & Services -> OAuth consent screen**. Choose **External**,
   fill in the required app name / your email, and save. Under **Test users**,
   add your own Gmail address (this keeps it in testing mode, which is fine).
4. Go to **APIs & Services -> Credentials -> Create Credentials -> OAuth client
   ID**. Application type: **Desktop app**. Create it.
5. Click **Download JSON** on the new credential. Rename the file to
   **`credentials.json`** and place it in this project folder (next to
   `gmail_client.py`).
6. Set `"source": "gmail"` and `"gmail_label": "Reels"` in `config.json`.

**First run** opens a browser asking you to allow access to your Gmail. Approve
it. A `token.json` is saved so every later run is silent — no browser, no login.

> `credentials.json` and `token.json` are gitignored. Never commit them.

### What the script touches in Gmail

It only reads messages under your Reels label and removes their **unread** flag
after a transcript is made (so they aren't reprocessed). It does not delete,
send, or read anything outside that label.

## How URLs get into the queue

The script reads any Instagram URL it finds in `queue_file`, one per line,
ignoring blank lines, `#` comments, and markdown/HTML. The iOS Shortcut emails
reel links to a Gmail label; for now you paste those links into the queue file.
(A later version can read Gmail directly.)

## Level 1 — run it manually

```bash
python reel_transcriber.py
```

It processes every new URL in the queue, skips ones it has already done
(tracked in `processed.json`), and writes one Markdown transcript per reel into
`output_dir`. Re-running is safe — it never re-transcribes the same reel twice.

## Level 2 — run it automatically (Windows Task Scheduler)

1. Edit `run_transcriber.bat` — set `PROJECT_DIR` to where this repo lives and
   `PYTHON` to your python path (`where python` to find it). If you used a venv,
   point `PYTHON` at `.venv\Scripts\python.exe`.
2. Open **Task Scheduler** -> **Create Task** (not "Basic Task").
   - **General:** name it "Reel Transcriber". Check **Run whether user is logged
     on or not**.
   - **Triggers:** New -> **On a schedule** -> Daily, repeat every 1 hour (or
     whatever cadence you like). Check **Enabled**.
   - **Settings tab:** check **Run task as soon as possible after a scheduled
     start is missed** — this is what makes it catch up after the laptop was
     asleep.
   - **Actions:** New -> Start a program -> browse to `run_transcriber.bat`.
3. Save. Enter your Windows password if prompted.

### Does it run while the laptop is asleep?

**No, not reliably.** Task Scheduler does not run during sleep by default, and
the "Wake the computer to run this task" option is flaky on battery and useless
from full shutdown. The realistic setup is the **"run as soon as possible after
a missed start"** option above: whenever the laptop is next awake, it catches up
on anything it missed. Reels aren't time-sensitive, so this is fine in practice.

## Caveats (honest ones)

- **Instagram + yt-dlp is finicky.** Public reels usually download; some require
  the `cookies_from_browser` setting to pass your login. Private/removed reels
  won't download at all — that's an Instagram restriction, not a bug here.
- **First run is slow.** Whisper downloads the model file once (a few hundred MB
  for `base`). After that it's cached.
- **Audio-only.** This captures the _spoken_ content. On-screen text that's never
  spoken aloud won't be transcribed.
- **Local compute.** Transcription uses your CPU. A 60-second reel on `base`
  takes roughly 10-30 seconds depending on the machine.

## Project layout

```
reel-transcriber/
├── reel_transcriber.py     # main script
├── gmail_client.py          # Gmail API reader (used when source = gmail)
├── config.example.json      # copy to config.json and edit
├── requirements.txt
├── run_transcriber.bat      # Task Scheduler wrapper (Level 2)
├── .gitignore
└── README.md
```

`config.json`, `credentials.json`, `token.json`, `processed.json`, and the log
are all gitignored so your personal paths, secrets, and state never end up on
GitHub.
