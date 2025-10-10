#!/usr/bin/env python3
"""Generate release metadata for the Mycelium CI pipeline.

This script collects pull request information to produce structured release
notes, determines the semantic version bump to apply, and calculates follow-up
versions for development branches. It expects to run inside the GitHub Actions
workflow with a full git checkout available.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import typing as t
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_START_DATE = "1970-01-01"
CATEGORY_LABELS = {
    "features": {"feature", "enhancement", "feat"},
    "fixes": {"fix", "fixes", "bug", "bugfix", "bug-fix", "hotfix"},
    "chores": {"chore", "maintenance", "refactor", "docs", "documentation"},
}
CATEGORY_EMOJI = {
    "features": "🚀",
    "fixes": "🐛",
    "chores": "🔧",
}
VERSION_BUMP_ORDER = {"major": 3, "minor": 2, "patch": 1}
ACCEPTED_LABEL_BUMPS = {
    "major": "major",
    "breaking change": "major",
    "minor": "minor",
    "feature": "minor",
    "enhancement": "minor",
    "hotfix": "patch",
    "patch": "patch",
    "fix": "patch",
    "bugfix": "patch",
}
RELEASE_LABEL_GATES = {"hotfix", "minor", "major"}


class ReleaseMetadataError(RuntimeError):
    """Raised when release metadata cannot be determined."""


def run_git(*args: str) -> str:
    """Run git command and return stdout stripped."""

    completed = subprocess.run(
        ["git", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        raise ReleaseMetadataError(
            f"git {' '.join(args)} failed: {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def get_project_metadata(path: str) -> tuple[str, str]:
    """Return the distribution name and version from ``pyproject.toml``."""

    try:
        import tomllib
    except ModuleNotFoundError as exc:  # pragma: no cover - Python <3.11 safety
        raise ReleaseMetadataError("Python 3.11+ is required for tomllib") from exc

    with open(path, "rb") as handle:
        data = tomllib.load(handle)
    project = data.get("project", {})
    try:
        name = project["name"]
        version = project["version"]
    except KeyError as exc:
        missing_key = exc.args[0]
        raise ReleaseMetadataError(
            f"Missing '{missing_key}' in pyproject.toml [project] table"
        ) from exc
    return name, version


def parse_semver(version: str) -> t.Tuple[int, int, int]:
    """Parse a semantic version (major.minor.patch) ignoring suffix."""

    base = version.split("-", maxsplit=1)[0]
    parts = base.split(".")
    if len(parts) != 3:
        raise ReleaseMetadataError(f"Unsupported version format: {version}")

    try:
        major, minor, patch = (int(piece) for piece in parts)
    except ValueError as exc:  # pragma: no cover - invalid semver edge case
        raise ReleaseMetadataError(f"Non-integer version component in {version}") from exc
    return major, minor, patch


def bump_version(version: str, bump_type: str) -> str:
    """Return the bumped version string for the given bump type."""

    major, minor, patch = parse_semver(version)
    if bump_type == "major":
        return f"{major + 1}.0.0"
    if bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    if bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ReleaseMetadataError(f"Unknown bump type: {bump_type}")


def next_dev_version(released_version: str) -> str:
    """Return the next development version (patch bump with -dev suffix)."""

    major, minor, patch = parse_semver(released_version)
    return f"{major}.{minor}.{patch + 1}-dev"


def github_request(url: str, token: str, params: t.Optional[dict[str, str]] = None) -> t.Tuple[dict, dict[str, str]]:
    """Perform a GitHub API request and return JSON + response headers."""

    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    try:
        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read())
            headers = {key: value for key, value in response.getheaders()}
            return payload, headers
    except urllib.error.HTTPError as exc:  # pragma: no cover - network edge case
        raise ReleaseMetadataError(
            f"GitHub API error {exc.code} for {url}: {exc.read().decode()}"
        ) from exc


def get_release_pr_number(repo: str, sha: str, token: str) -> t.Optional[int]:
    """Return the merged PR number associated with the commit."""

    url = f"https://api.github.com/repos/{repo}/commits/{sha}/pulls"
    payload, _ = github_request(url, token)
    if not payload:
        return None
    return payload[0]["number"]


def get_pull_request(repo: str, pr_number: int, token: str) -> dict[str, t.Any]:
    """Fetch pull request details."""

    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    payload, _ = github_request(url, token)
    return payload


def get_pr_labels(repo: str, pr_number: int, token: str) -> list[str]:
    """Fetch labels for a pull request."""

    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    payload, _ = github_request(url, token)
    labels = [label["name"].lower() for label in payload.get("labels", [])]
    return labels


def calculate_bump_type(
    labels: list[str],
    manual_bump: t.Optional[str],
    default_bump: str,
) -> str:
    """Determine bump type respecting manual overrides and label priority."""

    if manual_bump:
        manual = manual_bump.lower()
        if manual not in {"major", "minor", "patch"}:
            raise ReleaseMetadataError(f"Invalid manual bump type: {manual_bump}")
        return manual

    chosen: str = default_bump
    highest_score = VERSION_BUMP_ORDER[default_bump]
    for label in labels:
        mapped = ACCEPTED_LABEL_BUMPS.get(label)
        if not mapped:
            continue
        score = VERSION_BUMP_ORDER[mapped]
        if score > highest_score:
            chosen = mapped
            highest_score = score
    return chosen


def get_previous_tag() -> t.Optional[str]:
    """Return the previous release tag matching v* pattern."""

    try:
        return run_git("describe", "--tags", "--match", "v*", "--abbrev=0")
    except ReleaseMetadataError:
        return None


def get_tag_timestamp(tag: str) -> str:
    """Return tag commit timestamp in ISO 8601 format."""

    return run_git("log", "-1", "--format=%cI", tag)


def get_repo_first_commit_date() -> str:
    """Return the timestamp of the first commit."""

    return run_git("log", "--reverse", "--format=%cI", "--max-count", "1")


def search_merged_prs(
    repo: str,
    token: str,
    start_date: str,
    base_branch: str,
    exclude_numbers: set[int],
) -> list[dict[str, t.Any]]:
    """Search merged PRs after start_date for a specific base branch."""

    items: list[dict[str, t.Any]] = []
    page = 1
    while True:
        query = f"repo:{repo} is:pr is:merged merged:>={start_date} base:{base_branch}"
        payload, _ = github_request(
            "https://api.github.com/search/issues",
            token,
            {
                "q": query,
                "sort": "created",
                "order": "asc",
                "per_page": "100",
                "page": str(page),
            },
        )
        fetched = payload.get("items", [])
        for pr in fetched:
            number = pr["number"]
            if number in exclude_numbers:
                continue
            items.append(pr)
        if len(fetched) < 100:
            break
        page += 1
    return items


def categorize_prs(prs: list[dict[str, t.Any]]) -> dict[str, list[str]]:
    """Group PR titles by category labels."""

    results = {key: [] for key in CATEGORY_LABELS}
    results["other"] = []

    for pr in prs:
        title = pr.get("title", "Untitled PR")
        number = pr.get("number")
        label_names = [label["name"].lower() for label in pr.get("labels", [])]
        entry = f"- {title} (#{number})"

        matched = False
        for category, labels in CATEGORY_LABELS.items():
            if any(label in labels for label in label_names):
                results[category].append(entry)
                matched = True
        if not matched:
            results["other"].append(entry)
    return results


def format_preview_summary(
    release_version: str,
    bump_type: str,
    previous_tag: t.Optional[str],
    categories: dict[str, list[str]],
    open_pr: t.Optional[dict[str, t.Any]],
) -> str:
    """Create a concise summary suitable for PR preview comments."""

    total_entries = sum(len(entries) for entries in categories.values())
    lines: list[str] = []
    lines.append(f"## Release Preview for v{release_version}")
    lines.append("")
    lines.append(f"- **Bump type:** {bump_type.capitalize()}")
    if previous_tag:
        lines.append(f"- **Previous tag:** {previous_tag}")
        lines.append(
            f"- **Diff:** https://github.com/{os.environ['GITHUB_REPOSITORY']}/compare/{previous_tag}...v{release_version}"
        )
    lines.append(f"- **Total merged PRs considered:** {total_entries}")

    if open_pr:
        title = open_pr.get("title", "Unknown title")
        number = open_pr.get("number")
        html_url = open_pr.get("html_url")
        label_names = ", ".join(
            label.get("name", "") for label in open_pr.get("labels", [])
        ) or "None"
        lines.append(
            f"- **Current PR:** [{title}]({html_url}) (#{number})"
        )
        lines.append(f"- **Current PR labels:** {label_names}")

    lines.append("")

    order = (
        ("features", "🚀 Features"),
        ("fixes", "🐛 Fixes"),
        ("chores", "🔧 Chores"),
        ("other", "📝 Other Changes"),
    )

    for key, heading in order:
        lines.append(f"### {heading}")
        entries = categories.get(key) or []
        if entries:
            lines.extend(entries)
        else:
            lines.append("- _No matching pull requests_")
        lines.append("")

    return "\n".join(lines).rstrip()


def format_release_notes(
    categories: dict[str, list[str]],
    release_version: str,
    previous_tag: t.Optional[str],
    distribution_name: str,
) -> str:
    """Compose markdown release notes."""

    lines: list[str] = []
    lines.append(f"## What's Changed in v{release_version}")
    lines.append("")

    for category in ("features", "fixes", "chores"):
        emoji = CATEGORY_EMOJI[category]
        title = category.capitalize()
        lines.append(f"### {emoji} {title}")
        entries = categories.get(category) or []
        if entries:
            lines.extend(entries)
        else:
            lines.append("- _No pull requests labeled for this category_")
        lines.append("")

    other_entries = categories.get("other") or []
    if other_entries:
        lines.append("### 📝 Other Changes")
        lines.extend(other_entries)
        lines.append("")

    lines.append("### 📦 Installation")
    lines.append("```bash")
    lines.append(f"pip install {distribution_name}=={release_version}")
    lines.append("```")
    lines.append("")

    if previous_tag:
        lines.append(
            f"**Full Changelog**: https://github.com/{os.environ['GITHUB_REPOSITORY']}/compare/{previous_tag}...v{release_version}"
        )
    else:
        lines.append(
            f"**Full Changelog**: https://github.com/{os.environ['GITHUB_REPOSITORY']}/releases/tag/v{release_version}"
        )
    return "\n".join(lines)


def main() -> None:
    repository = os.environ["GITHUB_REPOSITORY"]
    sha = os.environ.get("GITHUB_SHA", "")
    token = os.environ.get("GITHUB_TOKEN")
    manual_bump = os.environ.get("MANUAL_BUMP")
    default_bump = os.environ.get("DEFAULT_BUMP", "patch").lower()
    include_open_pr = os.environ.get("INCLUDE_OPEN_PR", "false").lower() == "true"
    pull_request_number_raw = os.environ.get("PULL_REQUEST_NUMBER")

    if not token:
        raise ReleaseMetadataError("GITHUB_TOKEN environment variable is required")

    distribution_name, current_version = get_project_metadata("pyproject.toml")

    previous_tag = get_previous_tag()
    if previous_tag:
        base_version = previous_tag.lstrip("v")
        start_date = get_tag_timestamp(previous_tag)[:10]
    else:
        base_version = current_version
        start_date = get_repo_first_commit_date()[:10] if sha else DEFAULT_START_DATE

    release_pr_number: t.Optional[int] = None
    pr_labels: list[str] = []
    if sha:
        release_pr_number = get_release_pr_number(repository, sha, token)
        if release_pr_number:
            pr_labels = get_pr_labels(repository, release_pr_number, token)
    open_pr: t.Optional[dict[str, t.Any]] = None
    if include_open_pr and pull_request_number_raw:
        try:
            pull_request_number = int(pull_request_number_raw)
        except ValueError as exc:
            raise ReleaseMetadataError(
                f"Invalid pull request number: {pull_request_number_raw}"
            ) from exc
        open_pr = get_pull_request(repository, pull_request_number, token)
        if not pr_labels and open_pr:
            pr_labels = [label["name"].lower() for label in open_pr.get("labels", [])]

    release_label = next((label for label in pr_labels if label in RELEASE_LABEL_GATES), "")
    has_release_label = bool(release_label)

    bump_type = calculate_bump_type(pr_labels, manual_bump, default_bump)
    release_version = bump_version(base_version, bump_type)
    dev_version = next_dev_version(release_version)

    exclude = {release_pr_number} if release_pr_number else set()
    prs_develop = search_merged_prs(repository, token, start_date, "develop", exclude)
    prs_main = search_merged_prs(repository, token, start_date, "main", exclude)
    categorized = categorize_prs(prs_develop + prs_main)
    release_notes = format_release_notes(
        categorized,
        release_version,
        previous_tag,
        distribution_name,
    )
    preview_summary = format_preview_summary(
        release_version,
        bump_type,
        previous_tag,
        categorized,
        open_pr,
    )

    metadata = {
        "current_version": current_version,
        "base_version": base_version,
        "release_version": release_version,
        "next_dev_version": dev_version,
        "bump_type": bump_type,
        "release_pr_number": release_pr_number,
        "release_notes": release_notes,
        "preview_summary": preview_summary,
        "categorized_prs": categorized,
        "total_prs_considered": sum(len(entries) for entries in categorized.values()),
        "previous_tag": previous_tag,
        "start_date": start_date,
        "release_label": release_label,
        "has_release_label": has_release_label,
    }

    print(json.dumps(metadata))


if __name__ == "__main__":
    try:
        main()
    except ReleaseMetadataError as error:
        print(f"::error::{error}")
        sys.exit(1)
