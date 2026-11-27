"""The `killshot` command. Install it once with `pip install -e .`

    killshot start          run the app: site at http://localhost:8000, plus the worker. Ctrl-C stops it.
    killshot serve          the same on a server (Railway): no site build, no browser, open to the network
    killshot migrate        create the database if needed and apply migrations
    killshot test           run every test: Python (pytest) and the site (Vitest)
    killshot test python    just the Python tests; extra arguments go to pytest (e.g. -k worker)
    killshot test web       just the site's tests

    killshot load ...       load a team's finished games from CBBD   (`killshot load --help`)
    killshot inspect ...    print one game
    killshot season ...     print a season
    killshot worker         run only the worker
    killshot reprocess      rebuild stored games from their saved raw data
    killshot replay GAME    play a finished game back as if live (tests the live view)
    killshot openapi PATH   write the API schema (used by `npm run gen:api`)
    killshot vapid          generate a VAPID key pair for push notifications

Settings come from .env in the repo folder (copy .env.sample to start).
"""
import datetime as dt
import importlib
import os
import signal
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the repo folder: .env, web/, migrations/

# Subcommands that run an existing module's main(): `killshot load` -> killshot.load.main()
TOOLS = {name: f"killshot.{name}" for name in
         ("migrate", "load", "inspect", "season", "worker", "reprocess", "replay", "openapi", "vapid")}


def load_env(path: Path = ROOT / ".env") -> None:
    """Read KEY=value lines from .env into the environment. Variables already set win,
    so `DATABASE_URL=... killshot start` still overrides the file."""
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def require(*names: str) -> None:
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        hint = "Copy .env.sample to .env and fill it in." if not (ROOT / ".env").exists() else "Add them to .env."
        sys.exit(f"Missing {', '.join(missing)}. {hint}")


def run(*args: str, cwd: Path = ROOT) -> None:
    """Run a step and stop with a clear message if it fails."""
    if subprocess.run(args, cwd=cwd).returncode != 0:
        sys.exit(f"Failed: {' '.join(args)}")


def require_node() -> None:
    """Stop early, with a clear fix, if Node is missing or older than web/.nvmrc asks for."""
    wanted = int((ROOT / "web" / ".nvmrc").read_text().strip())
    try:
        version = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip()
    except FileNotFoundError:
        sys.exit(f"Node isn't installed. The site needs Node {wanted}: "
                 f"`nvm install {wanted}`, or `brew install node@{wanted}`.")
    if int(version.lstrip("v").split(".")[0]) < wanted:
        sys.exit(f"The site needs Node {wanted}, but this terminal has {version}. "
                 f"With asdf: `asdf install`. With nvm: `cd web && nvm install && nvm use`. "
                 f"Or `brew install node@{wanted}`.")


def build_site_if_needed() -> None:
    """Build the React site the first time, or when its source is newer than the last build."""
    web, built = ROOT / "web", ROOT / "web" / "dist" / "index.html"
    sources = [p for p in (web / "src").rglob("*") if p.is_file()] + [web / "package.json", web / "index.html"]
    if built.exists() and built.stat().st_mtime >= max(p.stat().st_mtime for p in sources):
        return
    require_node()
    print("Building the site (web/)...")
    if not (web / "node_modules").exists():
        run("npm", "ci", "--no-audit", "--no-fund", cwd=web)
    run("npm", "run", "build", cwd=web)


def has_games() -> bool:
    from . import db
    with db.connect(os.environ["DATABASE_URL"]) as conn:
        return conn.execute("SELECT count(*) FROM games WHERE plays_saved_at IS NOT NULL").fetchone()[0] > 0


def wait_for_site(url: str, seconds: int = 30) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"{url}/api/teams", timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def first_load() -> None:
    """The first time, load each tracked team's last two seasons (about 40 CBBD calls each)."""
    from .worker import current_season
    if has_games():
        return
    season = current_season(dt.date.today())  # e.g. 2027 for 2026-27
    for team in [t.strip() for t in os.environ.get("TRACKED_TEAMS", "Kansas").split(",") if t.strip()]:
        print(f"First start: loading {team}'s last two seasons (about 40 CBBD calls)...", flush=True)
        run(sys.executable, "-m", "killshot.load", "--team", team, "--seasons", str(season - 1), str(season))


def run_app(host: str, open_browser: bool) -> None:
    """Run the site and the worker side by side until Ctrl-C, SIGTERM, or one of them stops."""
    # Ctrl-C and a plain `kill` (or Railway replacing the service) both stop everything.
    signal.signal(signal.SIGINT, signal.default_int_handler)
    signal.signal(signal.SIGTERM, signal.default_int_handler)

    port = os.environ.get("PORT", "8000")
    url = f"http://localhost:{port}"
    processes = [
        subprocess.Popen([sys.executable, "-m", "killshot.worker"], cwd=ROOT),
        subprocess.Popen([sys.executable, "-m", "uvicorn", "killshot.api:app", "--host", host, "--port", port,
                          "--log-level", "warning"], cwd=ROOT),
    ]
    stopped_by_user = False
    try:
        if wait_for_site(url):
            print(f"\nKillshot is running at {url}   (Ctrl-C to stop)\n", flush=True)
            if open_browser:
                webbrowser.open(url)
        while all(p.poll() is None for p in processes):
            time.sleep(1)
        print("A process stopped unexpectedly; shutting down.", flush=True)
    except KeyboardInterrupt:
        stopped_by_user = True
    finally:
        # Already stopping: a second Ctrl-C or SIGTERM mustn't interrupt the cleanup.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        print("\nStopping...", flush=True)
        for p in processes:
            p.terminate()
        for p in processes:
            p.wait(timeout=15)
    if not stopped_by_user:
        sys.exit(1)  # so a server (Railway) restarts it


def backfill() -> None:
    """Fill in anything new the current code derives from games already stored
    (today: box scores), from their saved raw data. Usually does nothing."""
    from . import db
    from .reprocess import backfill_box_scores
    with db.connect(os.environ["DATABASE_URL"]) as conn:
        n = backfill_box_scores(conn)
    if n:
        print(f"Added box scores to {n} stored games.", flush=True)


def start(args: list[str]) -> None:
    """Migrate, build the site if needed, load history the first time, then run the site and worker."""
    require("DATABASE_URL", "CBBD_API_KEY")
    from . import migrate

    migrate.main()
    backfill()
    build_site_if_needed()
    first_load()
    run_app("127.0.0.1", open_browser="--no-open" not in args)


def serve(args: list[str]) -> None:
    """On a server: migrate, load history the first time, then run the site and worker.
    The site is built into the image beforehand (see Dockerfile), and listens on every
    network interface so the host's router can reach it."""
    require("DATABASE_URL", "CBBD_API_KEY")
    from . import migrate

    migrate.main()
    backfill()
    first_load()
    run_app("0.0.0.0", open_browser=False)


def test_plan(args: list[str]) -> tuple[list[str], list[str]]:
    """Which suites to run, and the extra arguments to pass along.
    `killshot test` -> both; `killshot test python -k worker` -> Python only, with `-k worker`."""
    if args and args[0] in ("python", "web"):
        return [args[0]], args[1:]
    return ["python", "web"], args


def check_test_database() -> str | None:
    """The test database URL, after making sure it's safe to wipe and exists.
    None if it isn't set (the Postgres tests are then skipped)."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        return None
    if url == os.environ.get("DATABASE_URL"):
        sys.exit("TEST_DATABASE_URL is the same as DATABASE_URL. The tests wipe their database, "
                 "so point TEST_DATABASE_URL at a separate one (e.g. .../killshot_test).")
    from . import db
    db.ensure_database(url)
    return url


def test(args: list[str]) -> None:
    """Run the Python and/or site tests, then print one summary line per suite."""
    suites, extra = test_plan(args)
    results: dict[str, bool] = {}
    if "python" in suites:
        if check_test_database() is None:
            print("TEST_DATABASE_URL isn't set, so the Postgres tests will be skipped. See .env.sample.")
        results["Python"] = subprocess.run([sys.executable, "-m", "pytest", *extra], cwd=ROOT).returncode == 0
    if "web" in suites:
        web = ROOT / "web"
        require_node()
        if not (web / "node_modules").exists():
            run("npm", "ci", "--no-audit", "--no-fund", cwd=web)
        npm_args = ["npm", "test", *(["--", *extra] if suites == ["web"] and extra else [])]
        # Same time zone as CI, so date tests behave identically everywhere.
        results["Site"] = subprocess.run(npm_args, cwd=web, env={**os.environ, "TZ": "UTC"}).returncode == 0

    print("\n" + "   ".join(f"{name}: {'passed' if ok else 'FAILED'}" for name, ok in results.items()))
    if not all(results.values()):
        sys.exit(1)


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__.strip())
        return
    load_env()
    name, rest = argv[0], argv[1:]
    if name == "start":
        start(rest)
    elif name == "serve":
        serve(rest)
    elif name == "test":
        test(rest)
    elif name in TOOLS:
        asking_for_help = any(a in ("-h", "--help") for a in rest)
        if name in ("migrate", "load", "season", "worker", "reprocess", "replay") and not asking_for_help:
            require("DATABASE_URL")
        sys.argv = [f"killshot {name}", *rest]  # so each tool's --help shows the right name
        importlib.import_module(TOOLS[name]).main()
    else:
        sys.exit(f"Unknown command '{name}'. Run `killshot --help` to see the commands.")


if __name__ == "__main__":
    main()
