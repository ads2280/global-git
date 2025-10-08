from __future__ import annotations

import os
import sys
from setuptools import setup
from setuptools.command.develop import develop as _develop
from setuptools.command.install import install as _install


def _run_post_install():
    if os.environ.get("GLOBAL_GIT_NO_PATH", "0") in {"1", "true", "True"}:
        return
    try:
        # Execute the installed helper as a module to ensure correct environment
        os.system(f"{sys.executable} -m global_git.post_install || true")
    except Exception:
        # Best-effort; do not fail installation
        pass


class install(_install):
    def run(self):
        super().run()
        _run_post_install()


class develop(_develop):
    def run(self):
        super().run()
        _run_post_install()


if __name__ == "__main__":
    setup(cmdclass={"install": install, "develop": develop})
