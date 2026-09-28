"""Stable Gradle releases from the official release service."""
import json
import re
from urllib.request import urlopen

DEFAULT_GRADLE = "9.8.0"
# Offline snapshot of the current 9.x and 8.x release lines (2026-09-28).
FALLBACK_VERSIONS = "9.8.0 9.7.1 9.7.0 9.6.1 9.6.0 9.5.1 9.5.0 9.4.1 9.4.0 9.3.1 9.3.0 9.2.1 9.2.0 9.1.0 9.0.0 8.14.5 8.14.4 8.14.3 8.14.2 8.14.1 8.14 8.13 8.12.1 8.12 8.11.1 8.11 8.10.2 8.10.1 8.10 8.9 8.8 8.7 8.6 8.5 8.4 8.3 8.2.1 8.2 8.1.1 8.1 8.0.2 8.0.1 8.0".split()


def stable_versions(releases):
    versions = {
        item["version"] for item in releases
        if re.fullmatch(r"\d+\.\d+(?:\.\d+)?", item.get("version", ""))
        and not any(item.get(flag) for flag in ("snapshot", "nightly", "broken"))
    }
    return sorted(versions, key=lambda v: tuple(map(int, v.split("."))), reverse=True)


def fetch_versions():
    with urlopen("https://services.gradle.org/versions/all", timeout=10) as response:
        versions = stable_versions(json.load(response))
    if not versions:
        raise ValueError("No stable Gradle releases returned")
    return versions
