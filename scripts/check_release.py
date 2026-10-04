"""Check Git publication candidates for private/generated deployment artifacts."""

from pathlib import Path, PurePosixPath
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PREFIXES = ("data/auth/", "data/runtime/", "data/evaluations/", "data/deployment-check/", ".venv/")


def forbidden(name):
    path = PurePosixPath(name.replace("\\", "/"))
    value = path.as_posix()
    return (path.is_absolute() or ".." in path.parts or
            value.startswith(PRIVATE_PREFIXES) or
            (path.name.startswith(".env") and path.name != ".env.example") or
            path.suffix.lower() in {".sqlite", ".sqlite3", ".db", ".log"} or
            path.name == "bootstrap-credentials.txt")


def main():
    result = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                            cwd=ROOT, capture_output=True, check=True)
    candidates = set(result.stdout.decode().split("\0")) - {""}
    rejected = sorted(name for name in candidates if forbidden(name) or (ROOT / name).is_symlink())
    if rejected:
        # Print only paths, never secret contents.
        print("FAIL private/generated files or symlinks in publication candidates:")
        print("\n".join(rejected))
        raise SystemExit(1)
    print(f"PASS {len(candidates)} Git publication candidates; private deployment paths excluded")
    print("Path-based guard only; review source contents for secrets before publishing")


if __name__ == "__main__":
    main()
