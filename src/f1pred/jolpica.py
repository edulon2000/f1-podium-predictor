"""Client for the Jolpica-F1 API (Ergast-compatible): http://api.jolpi.ca/ergast/f1/"""

from __future__ import annotations

from typing import Any

from f1pred.http import CachedClient
from f1pred.schema import SchemaError, req

BASE_URL = "https://api.jolpi.ca/ergast/f1"
PAGE_LIMIT = 100  # Jolpica's maximum page size

# endpoint -> key of the per-race list inside each Race object
RACE_ENDPOINTS = {
    "results": "Results",
    "qualifying": "QualifyingResults",
    "sprint": "SprintResults",
}


class Jolpica:
    def __init__(self, client: CachedClient, base_url: str = BASE_URL) -> None:
        self.client = client
        self.base_url = base_url.rstrip("/")

    def _get(self, path: str, offset: int, max_age: float | None) -> dict:
        url = f"{self.base_url}/{path}.json"
        body = self.client.get_json(url, {"limit": PAGE_LIMIT, "offset": offset}, max_age=max_age)
        return req(body, "MRData", url)

    def _paginate(self, path: str, max_age: float | None) -> list[dict]:
        pages = [self._get(path, 0, max_age)]
        total = int(req(pages[0], "total", path))
        offset = PAGE_LIMIT
        while offset < total:
            pages.append(self._get(path, offset, max_age))
            offset += PAGE_LIMIT
        return pages

    def schedule(self, season: int, max_age: float | None = None) -> list[dict]:
        races: list[dict] = []
        for page in self._paginate(str(season), max_age):
            races.extend(req(req(page, "RaceTable", "schedule"), "Races", "schedule"))
        return races

    def season_races(self, season: int, endpoint: str, max_age: float | None = None) -> list[dict]:
        """All races of a season for results/qualifying/sprint.

        Pagination counts result *rows*, so one race can be split across two pages; the pieces
        are merged back by (season, round).
        """
        list_key = RACE_ENDPOINTS[endpoint]
        merged: dict[tuple[int, int], dict[str, Any]] = {}
        expected_rows = None
        for page in self._paginate(f"{season}/{endpoint}", max_age):
            expected_rows = int(page["total"])
            for race in req(req(page, "RaceTable", endpoint), "Races", endpoint):
                key = (int(race["season"]), int(race["round"]))
                if key in merged:
                    merged[key][list_key].extend(req(race, list_key, endpoint))
                else:
                    merged[key] = {**race, list_key: list(req(race, list_key, endpoint))}
        got = sum(len(r[list_key]) for r in merged.values())
        if expected_rows is not None and got != expected_rows:
            raise SchemaError(
                f"{season}/{endpoint}: expected {expected_rows} rows, got {got} after pagination"
            )
        return [merged[k] for k in sorted(merged)]

    def standings(
        self, season: int, rnd: int, kind: str, max_age: float | None = None
    ) -> dict:
        """kind = 'driverStandings' | 'constructorStandings'. Standings *after* that round."""
        if kind not in ("driverStandings", "constructorStandings"):
            raise ValueError(kind)
        pages = self._paginate(f"{season}/{rnd}/{kind}", max_age)
        if len(pages) != 1:
            raise SchemaError(f"{season}/{rnd}/{kind}: unexpected pagination ({len(pages)} pages)")
        return pages[0]
