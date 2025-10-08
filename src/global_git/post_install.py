from __future__ import annotations

import datetime as _dt
import os
import shlex
import sys
import sysconfig


RC_CANDIDATES = [
    ("zsh", os.path.join(os.path.expanduser("~"), ".zshrc")),
    ("bash", os.path.join(os.path.expanduser("~"), ".bashrc")),
    ("bash", os.path.join(os.path.expanduser("~"), ".bash_profile")),
    ("sh", os.path.join(os.path.expanduser("~"), ".profile")),
]


def _detect_rc_file() -> str | None:
    shell = os.environ.get("SHELL", "").split("/")[-1]
    # Prefer matching shell; otherwise fall back to first existing candidate
    for sh, path in RC_CANDIDATES:
        if shell == sh:
            return path
    for _sh, path in RC_CANDIDATES:
        if os.path.exists(path):
            return path
    # Default to zshrc on macOS-like environments
    return os.path.join(os.path.expanduser("~"), ".zshrc")


def _ensure_path_line(content: str, scripts_dir: str) -> str:
    marker_begin = "# >>> global-git PATH >>>"
    marker_end = "# <<< global-git PATH <<<"
    export_line = f'export PATH="{scripts_dir}:$' + '{PATH}"\n'
    block = (
        f"{marker_begin}\n"
        f"# Added by global-git on {_dt.date.today().isoformat()}\n"
        f"if ! echo \"$PATH\" | tr ':' '\n' | grep -qx {shlex.quote(scripts_dir)}; then\n"
        f"  {export_line}"
        f"fi\n"
        f"{marker_end}\n"
    )

    if marker_begin in content and marker_end in content:
        # Replace existing block
        start = content.index(marker_begin)
        end = content.index(marker_end) + len(marker_end)
        before = content[:start]
        after = content[end:]
        return before + block + after
    else:
        if not content.endswith("\n"):
            content += "\n"
        return content + "\n" + block


def configure_path(scripts_dir: str) -> bool:
    rc = _detect_rc_file()
    try:
        current = ""
        if os.path.exists(rc):
            with open(rc, "r", encoding="utf-8") as f:
                current = f.read()
        updated = _ensure_path_line(current, scripts_dir)
        if updated != current:
            with open(rc, "w", encoding="utf-8") as f:
                f.write(updated)
        return True
    except Exception:
        return False


def main() -> int:
    # Determine the scripts dir where console_scripts are installed
    scripts_dir = sysconfig.get_path("scripts") or os.path.dirname(sys.executable)

    # If our scripts dir is already in PATH, we skip
    paths = os.environ.get("PATH", "").split(os.pathsep)
    norm_paths = [os.path.realpath(p) for p in paths]
    if os.path.realpath(scripts_dir) in norm_paths:
        return 0

    ok = configure_path(scripts_dir)
    if not ok:
        # Best-effort: print guidance
        sys.stderr.write(
            "global-git: could not update shell PATH automatically.\n"
            f"Add the following to your shell rc file:\n\n    export PATH=\"{scripts_dir}:$PATH\"\n\n"
        )
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

