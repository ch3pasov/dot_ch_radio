"""Ephemeral playback status derived from the declarative content tree."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


class RadioPlaybackStatus:
    """Map the active technical stream source back to its public station name."""

    def __init__(self, routes: Mapping[str, Mapping[str, Any]]):
        station_names_by_url: dict[str, str] = {}
        for route in routes.values():
            url = route.get("radio_url")
            if url is None:
                continue
            name = route.get("name")
            if not isinstance(url, str) or not url:
                raise ValueError("radio_url must be a non-empty string")
            if not isinstance(name, str) or not name:
                raise ValueError("Every radio station must have a non-empty name")
            previous_name = station_names_by_url.get(url)
            if previous_name is not None and previous_name != name:
                raise ValueError(
                    f"Radio URL {url!r} has conflicting names: "
                    f"{previous_name!r} and {name!r}"
                )
            station_names_by_url[url] = name

        self._station_names_by_url = station_names_by_url
        self._current_station_name: str | None = None

    @property
    def current_station_name(self) -> str | None:
        return self._current_station_name

    def record_stream(self, media: str | Path) -> None:
        """Record a successfully started source without persisting runtime state."""

        if isinstance(media, str):
            self._current_station_name = self._station_names_by_url.get(media)
        else:
            self._current_station_name = None
