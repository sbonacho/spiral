# spiral

Turn the recordings of your radio show into a podcast and social posts, from your terminal: add intro and outro, make the mp3, transcribe, summarize, cut vertical clips, and publish to podcast platforms and social networks, with several accounts per network.

[Español](README.es.md)

## Install

```bash
curl -LsSf https://raw.githubusercontent.com/sbonacho/spiral/main/install.sh | bash
```

macOS on Apple Silicon only (transcription runs locally with MLX). The script installs [uv](https://docs.astral.sh/uv/) if you don't have it, installs `spiral` as a global tool, makes sure the tool folder is on your `PATH`, and creates `~/.config/spiral/.env` for your global settings. It never uses `sudo` and never overwrites your configuration (it only removes the `# >>> spiral >>>` alias block that early versions added to `~/.zshrc`, `~/.bash_profile` or `~/.bashrc`, because it would hide the new command). Run it again to update; it is [short enough to read first](install.sh). Remove with `uv tool uninstall spiral-cli`.

You also need `ffmpeg` (`brew install ffmpeg`) and a summary provider (see [Summaries](#summaries)).

> **Status: beta.** Processing, state handling and the interface are covered by automated tests. The network destinations (YouTube, Bluesky, Mastodon, Instagram, Archive.org) are tested against mocked APIs only: do your first publication with `--dry-run`, then with one destination.

## What it does

For each `.mov` recorded with OBS (or any tool):

1. Adds your `intro.mov` and `outro.mov` if you have them, and normalizes the volume.
2. Exports an mp3.
3. Transcribes it locally with Whisper (free, private).
4. Writes a title, summaries, chapters, a tweet thread, a blog post and clip suggestions with the AI provider you choose.
5. Cuts vertical 9:16 clips with burned-in subtitles.
6. Publishes to any combination of: audio + blog + RSS feed (Archive.org and GitHub Pages), YouTube (episode and Shorts), Bluesky, Mastodon, Instagram Reels, X and TikTok (the last two assisted by hand).

Everything is free to run except what you choose to pay for (an LLM API, if you pick one).

## Quick start

`spiral` always works on the **current directory**: your recordings, your settings and your results live together, so one directory is one show.

```bash
cd ~/Movies/my-show
curl -o .env https://raw.githubusercontent.com/sbonacho/spiral/main/src/spiral/env.example   # then edit it
spiral
```

The menu shows which destinations are configured and which are not (and what each one is missing), then lets you pick an action with the arrow keys. Every action also works without the menu:

| Command | What it does |
|---|---|
| `spiral list` | Files in the directory with their state: pending, processed, published (and where). |
| `spiral process [name...] [--redo]` | Process one or more files. Tick them in a list (space ticks, Ctrl-A all, type to filter). |
| `spiral publish [name...] [--to a,b] [--dry-run] [--force] [--yes]` | Tick one or more processed episodes and the destinations (space ticks, `a` all; only configured ones can be ticked), then publish or simulate. Already-published destinations are skipped; `--force` (or answering yes in the menu) publishes them again. |
| `spiral unpublish [name...] [--from a,b] [--dry-run] [--yes]` | Remove publications you made by mistake. Deletes the post on Bluesky and Mastodon and takes the episode out of the site and feed; YouTube, Instagram, X and TikTok must be deleted by hand (spiral then asks to forget them). The mp3 stays on Archive.org. Always asks first. |
| `spiral view [--no-open]` | HTML report of every file, its state and where it is published. |
| `spiral --version` | Version. |

Scripting example (no terminal needed): `spiral publish 2026-11-01_show --to site,bluesky/show --yes`. Without a terminal and without the needed arguments, spiral exits with code 2 and a usage message.

## How it works

State is deduced from folders, with no database:

```
my-show/
├── 2026-11-01_show.mov        pending: a recording waiting to be processed
├── intro.mov  outro.mov       optional, added to every episode
├── .env                       local settings
├── processed/<name>/          processed: episodio.mov, episodio.mp3, transcripcion.{txt,srt,json},
│                              contenido.json (summary and posts), clips/, and the original .mov
├── published/<name>/          published: state.json (per destination), publish.log, report.html
└── site/                      blog, feed.xml and clips, created by the `site` destination
```

- Processing builds everything in a temporary folder and, only when it is complete, moves it to `processed/<name>/` and moves your original `.mov` inside. If something fails the original stays where it was, and a retry reuses what was already done (it won't transcribe twice).
- `contenido.json` is yours to edit before publishing. Re-processing an episode (`--redo`) asks first because it regenerates that file; what you already published is kept.
- Folder names can be changed with `PROCESSED_DIR` and `PUBLISHED_DIR` (relative paths inside the directory only).

### Configuration layers

Settings are read, variable by variable, from (highest first): the process environment, `.env` in the current directory, and `~/.config/spiral/.env`. Empty values are ignored. Put keys you share across shows (Archive.org, summary provider) in the global file and per-show things in the local one. `intro.mov` and `outro.mov` follow the same rule: the local file wins, then `~/.config/spiral/`.

### Destinations: networks and accounts

Each network can have several accounts. Declare them with `<NETWORK>_ACCOUNTS` and give each one its variables, for example:

```
BLUESKY_ACCOUNTS=show,personal
BLUESKY_SHOW_HANDLE=myshow.bsky.social
BLUESKY_SHOW_APP_PASSWORD=...
BLUESKY_PERSONAL_HANDLE=me.bsky.social
BLUESKY_PERSONAL_APP_PASSWORD=...
```

Destinations are written `network/account` (`bluesky/show`). The audio/blog/RSS destination is just `site` (one per show). A destination is configured only when all its variables exist; otherwise it is shown disabled with what it lacks. Publishing is idempotent: a destination already published is skipped, a failure in one destination doesn't stop the others, and partial progress (for instance, Shorts already uploaded) is remembered. `--dry-run` shows what would be sent without contacting anything or writing any state.

Tokens that spiral generates (YouTube authorization, the renewed Instagram token) are stored in `~/.config/spiral/tokens/` with `600` permissions, never next to your recordings. Logs never contain secrets.

## Setting up each destination

Do the one-time setup, then fill `.env` (see [`env.example`](src/spiral/env.example) for every variable).

### Audio, blog and RSS (`site`)

1. Create a public GitHub repository for the show and enable *Settings → Pages → Deploy from a branch → `main` / root*. Set `SITE_URL=https://<user>.github.io/<repo>` and the `PODCAST_*` variables.
2. Make `site/` that repository (spiral creates the files; you connect it): `mkdir site && cd site && git init -b main && git remote add origin git@github.com:<user>/<repo>.git`.
3. Get your Archive.org keys at <https://archive.org/account/s3.php> and set `IA_ACCESS_KEY` and `IA_SECRET_KEY` (or run `uv tool run --from internetarchive ia configure`).
4. Publish your first episode, then **submit `SITE_URL/feed.xml` once** to the directories you want: Spotify for Creators ("I already have a podcast"), Apple Podcasts Connect, iVoox ("import from RSS"), Amazon Music for Podcasters, Podcast Index (which Pocket Casts and others read), and optionally YouTube Music. After that, every `site` publication updates them all. Cover art (`PODCAST_IMAGE`): a square JPG or PNG, 1400–3000 px.

After every publication or removal, spiral also refreshes the site: each episode page shows badges with the logo of every network it was published to (linked when the link is known: YouTube, Bluesky, Mastodon), and the home page (`index.md`) becomes the episode list with the same badges (only if it is still the default one; a customised `index.md` is never touched). If `PODCAST_IMAGE` is set, it is also used as the site logo in the header. The generated styles live in `_sass/spiral.scss`; put your own after the `@import` in `assets/main.scss`. YouTube links only work for visitors once you make the video public in Studio.

When `site/` is its own git repository spiral offers to commit and push it after generating files; otherwise it only generates them.

### YouTube

Uploads the episode and each clip as a Short, **private**: an unaudited Google project cannot publish public videos through the API, so you make them public in YouTube Studio (one click) or apply for the free API audit.

1. In [Google Cloud Console](https://console.cloud.google.com) create a project and enable **YouTube Data API v3**.
2. Configure the OAuth consent screen (External), add yourself as a test user, then **publish the app ("In production")**; otherwise authorization expires every 7 days.
3. Create an **OAuth client ID** of type *Desktop app* and download its JSON to `~/.config/spiral/client_secret.json` (or set `YOUTUBE_<ACCOUNT>_CLIENT_SECRET`).
4. Add `YOUTUBE_ACCOUNTS=channel`. The first publication opens the browser to authorize.

The daily API quota (10,000 units) is enough for several uploads a day; the exact cost per upload varies between sources, so check the Cloud Console.

### Bluesky

*Settings → Privacy and security → App passwords → Add*. Use `BLUESKY_<ACCOUNT>_HANDLE` and `BLUESKY_<ACCOUNT>_APP_PASSWORD` (never your account password).

### Mastodon

*Preferences → Development → New application*, scope `write:statuses`, copy the access token. Use `MASTODON_<ACCOUNT>_URL` (your instance, e.g. `https://mastodon.social`; a profile URL is reduced to the instance) and `MASTODON_<ACCOUNT>_TOKEN`.

### Instagram Reels

Needs a professional (creator or business) account and a Meta app with the **Instagram Login** product, permission `instagram_business_content_publish`. For your own account the app can stay in development mode without Meta review. Generate a long-lived token and your Instagram account ID, and set `INSTAGRAM_<ACCOUNT>_USER_ID` and `INSTAGRAM_<ACCOUNT>_TOKEN`; spiral renews the token on every use (it expires after 60 days without use).

Instagram only accepts videos from a public URL, so spiral copies the clips to `site/media/`, pushes the site and waits until they are served by GitHub Pages. `site/` must therefore be a git repository published with Pages. Meta's published daily limits differ between its own pages (50 vs 100 posts per 24 h); you will not get near either.

### X and TikTok

Neither has free automatic posting. For X, spiral shows the pre-filled post links for the thread; for TikTok it opens the clips folder. In both cases it asks whether you have done it and, only if you confirm, records it as published (shown as "manual" in the report).

## Summaries

Set `LLM_PROVIDER`:

| Provider | Needs | Notes |
|---|---|---|
| `claude` (default) | The [`claude` CLI](https://claude.com/claude-code) logged in | Uses your Claude plan; `CLAUDE_MODEL` to change the model (default `claude-sonnet-5-5`). |
| `gemini` | `GEMINI_API_KEY` (optional `GEMINI_MODEL`) | Free tier available; check Google's terms about data use. |
| `ollama` | `OLLAMA_MODEL` and a local Ollama (`OLLAMA_URL` optional) | Fully offline, nothing leaves your machine. |

**Language:** `PODCAST_LANGUAGE` (default `es`) sets the language of the transcript and the generated texts, and also of spiral's own messages, prompts, help and report: Spanish for `es` (and `es-MX`...), English for `en` and for any other language.

**Privacy:** with `claude` and `gemini` the full transcript is sent to that provider; spiral prints which one before sending. The summary and the posts are written in `PODCAST_LANGUAGE` (default `es`), which is also the transcription language.

## Known limits

- macOS on Apple Silicon only. The first install is large (Whisper pulls in PyTorch), and the first transcription downloads a ~1.5 GB model.
- The `site` destination relies on GitHub Pages serving `feed.xml` as a static file next to the Jekyll theme; check that `SITE_URL/feed.xml` loads after the first publication.
- Third-party APIs change (YouTube quotas, Instagram permissions, X pricing). Each destination is isolated, so a change breaks only that one.
- `.env` files can hold secrets next to your recordings: keep them out of git (the provided `.gitignore` does).

## Development

```bash
git clone https://github.com/sbonacho/spiral && cd spiral
uv run --with-editable . --with pytest --with pexpect pytest
```

The design and requirements live in [`openspec/`](openspec/) (change `workspace-cli`); [`docs/design.md`](docs/design.md) keeps the original research (in Spanish). Contributions are welcome; please open an issue first for large changes.

## License

[MIT](LICENSE)
