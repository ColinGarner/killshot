"""The `killshot` command (installed by `pip install -e .`).

    killshot start          the whole app in Docker: database, site and worker, at http://localhost:8000
    killshot stop           stop it (your data stays in Docker's volume)
    killshot logs           follow the site's and worker's logs

    killshot load ...       load a team's finished games from CBBD   (see `killshot load --help`)
    killshot inspect ...    print one game
    killshot season ...     print a season
    killshot worker         run the worker directly (outside Docker)
    killshot migrate        apply database migrations
    killshot reprocess      rebuild stored games from their saved raw data
    killshot openapi PATH   write the API schema (used by `npm run gen:api`)
"""
import datetime as dt
import importlib
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

from .worker import current_season

SITE = "http://localhost:8000"

# Subcommands that run an existing module's main(), e.g. `killshot load` -> killshot.load.
MODULES = {name: f"killshot.{name}" for name in
           ("load", "inspect", "season", "worker", "migrate", "reprocess", "openapi")}


# --- start / stop / logs -------------------------------------------------------

def repo_root() -> Path:
    """The checkout holding docker-compose.yml: from the current folder upward, else next to this code."""
    for folder in [Path.cwd(), *Path.cwd().parents, Path(__file__).resolve().parent.parent]:
        if (folder / "docker-compose.yml").is_file():
            return folder
    sys.exit("Can't find docker-compose.yml. Run this from inside your killshot checkout.")


def read_env(path: Path) -> dict[str, str]:
    """KEY=value lines from a .env file (comments and blank lines ignored)."""
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def compose(root: Path, *args: str, capture: bool = False) -> subprocess.CompletedProcess:
    """Run `docker compose ...` in the checkout."""
    return subprocess.run(["docker", "compose", *args], cwd=root, check=not capture, text=True,
                          capture_output=capture)


def require_docker() -> None:
    if shutil.which("docker") is None:
        sys.exit("Docker isn't installed. Install Docker Desktop, start it, then run `killshot start` again.")
    if subprocess.run(["docker", "info"], capture_output=True).returncode != 0:
        sys.exit("Docker isn't running. Start Docker Desktop, then run `killshot start` again.")


def wait_for_site(seconds: int = 180) -> bool:
    """True once the site answers at all (its health may still say the worker hasn't checked in)."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"{SITE}/api/teams", timeout=3)
            return True
        except Exception:
            time.sleep(2)
    return False


def games_with_plays(root: Path) -> int:
    result = compose(root, "exec", "-T", "db", "psql", "-U", "killshot", "-tAc",
                     "SELECT count(*) FROM games WHERE plays_saved_at IS NOT NULL", capture=True)
    return int(result.stdout.strip() or 0) if result.returncode == 0 else 0


def start(args: list[str]) -> None:
    root = repo_root()
    require_docker()

    env_file = root / ".env"
    if not env_file.exists():
        shutil.copy(root / ".env.example", env_file)
        sys.exit(f"Created {env_file}. Put your CollegeBasketballData key after CBBD_API_KEY=, "
                 "then run `killshot start` again.")
    env = read_env(env_file)
    if not env.get("CBBD_API_KEY"):
        sys.exit(f"Add your CollegeBasketballData key after CBBD_API_KEY= in {env_file}, "
                 "then run `killshot start` again.")

    print("Building and starting the database, site and worker (the first build takes a few minutes)...")
    compose(root, "up", "--build", "--detach")
    if not wait_for_site():
        sys.exit("The site didn't come up. See what happened with `killshot logs`.")

    if games_with_plays(root) == 0:
        season = current_season(dt.date.today())        # e.g. 2027 for 2026-27
        last_season = f"{season - 2}-{str(season - 1)[2:]}"  # e.g. "2025-26"
        teams = [t.strip() for t in env.get("TRACKED_TEAMS", "Kansas").split(",") if t.strip()]
        print(f"First start: loading {last_season} and this season for {', '.join(teams)} "
              "(about 40 CBBD calls per team, a minute or two)...")
        for team in teams:
            compose(root, "run", "--rm", "worker", "python", "-m", "killshot.load",
                    "--team", team, "--seasons", str(season - 1), str(season))

    print(f"\nKillshot is running at {SITE}")
    print("  killshot logs   follow what the site and worker are doing")
    print("  killshot stop   stop it (your data is kept)")
    if "--no-open" not in args:
        webbrowser.open(SITE)


def stop(args: list[str]) -> None:
    compose(repo_root(), "down")
    print("Stopped. Your data is kept; `killshot start` brings it back.")


def logs(args: list[str]) -> None:
    try:
        compose(repo_root(), "logs", "--follow", "--tail", "50", "web", "worker")
    except KeyboardInterrupt:
        pass


COMMANDS = {"start": start, "stop": stop, "logs": logs}


# --- dispatch ------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__.strip())
        return
    name, rest = argv[0], argv[1:]
    if name in COMMANDS:
        COMMANDS[name](rest)
    elif name in MODULES:
        sys.argv = [f"killshot {name}", *rest]  # so each tool's --help shows the right name
        importlib.import_module(MODULES[name]).main()
    else:
        sys.exit(f"Unknown command '{name}'. Run `killshot --help` to see the commands.")


if __name__ == "__main__":
    main()
