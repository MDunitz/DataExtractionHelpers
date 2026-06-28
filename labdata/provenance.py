"""Provenance helpers."""

import subprocess


def get_git_revision_short_hash() -> str:
    """Short git commit hash of HEAD.

    Runs `git` in the CURRENT WORKING DIRECTORY, so in an installed package this
    reflects the *consumer's* working tree (the intended provenance), not the
    labdata package's.
    """
    return (
        subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])
        .decode("ascii")
        .strip()
    )
