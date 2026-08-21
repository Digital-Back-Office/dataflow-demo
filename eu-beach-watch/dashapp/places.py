"""
Place search for EU Beach Watch.

Beach names in the EEA source data are inconsistent and often don't mention
the town people actually know ("Plage de Sud" tells a tourist nothing). This
module lets users search by *place* instead: they type their hometown
("Bordeaux", or even a typo like "bordeux", or the native name of a Greek
village) and we resolve it to coordinates so the app can show every bathing
site near that place.

How it works:
- On first use we download GeoNames' cities500 dataset (every city/town/
  village with population >= 500 worldwide, ~13 MB zipped), keep only the
  European countries the app covers, and cache the parsed result on disk.
- Every place name — main name, ASCII name, and all alternate/native names —
  goes into one lookup table with its population.
- search_places() does exact lookup first, then fuzzy matching (difflib) over
  main names, weighted by population so "paris" resolves to Paris and not a
  tiny Parishville somewhere.

GeoNames data is CC-BY 4.0 (https://www.geonames.org).
"""

import difflib
import io
import logging
import os
import zipfile

import numpy as np
import pandas as pd
import requests

logger = logging.getLogger(__name__)

GEONAMES_URL = "http://download.geonames.org/export/dump/cities500.zip"
GEONAMES_LICENSE_NOTE = "Place data © GeoNames (CC-BY 4.0)"

# Same coverage as COUNTRY_NAMES in app.py — places outside these countries
# are useless to an EU bathing-water map, and dropping them keeps the
# in-memory index small.
EUROPEAN_CC = {
    "AL", "AT", "BE", "BG", "CH", "CY", "CZ", "DE", "DK", "EE", "EL", "ES",
    "FI", "FR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PL",
    "PT", "RO", "SE", "SI", "SK",
}

# GeoNames uses ISO codes except Greece, which it codes 'GR' while the EEA
# data (and COUNTRY_NAMES in app.py) uses 'EL'. Normalise so display works.
CC_ALIASES = {"GR": "EL"}

CACHE_FILENAME = "eu_cities_geonames.parquet"


def _cache_path() -> str:
    cache_dir = os.environ.get("BEACH_WATCH_CACHE_DIR", "/tmp/beach_watch_cache")
    return os.path.join(cache_dir, CACHE_FILENAME)


def _download_gazetteer() -> pd.DataFrame:
    """Download + parse cities500.zip, keeping only European rows we need."""
    logger.info("Downloading GeoNames gazetteer (%s)...", GEONAMES_URL)
    resp = requests.get(GEONAMES_URL, timeout=60,
                        headers={"User-Agent": "eu-beach-watch"})
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        txt_name = next(n for n in zf.namelist() if n.endswith(".txt"))
        with zf.open(txt_name) as fh:
            df = pd.read_csv(
                fh, sep="\t", header=None, dtype=str, encoding="utf-8",
                usecols=[1, 2, 3, 4, 5, 6, 8, 14],
                names=["name", "asciiname", "alternatenames", "lat", "lon",
                       "feature_class", "country_code", "population"],
                quoting=3,  # QUOTE_NONE — fields can contain stray quotes
            )

    df = df[df["country_code"].isin(EUROPEAN_CC | set(CC_ALIASES))]
    df["country_code"] = df["country_code"].replace(CC_ALIASES)
    df["lat"] = df["lat"].astype(float)
    df["lon"] = df["lon"].astype(float)
    df["population"] = pd.to_numeric(df["population"], errors="coerce").fillna(0).astype("int64")
    # One row per geoname id isn't guaranteed unique across name variants;
    # dedupe on the identity columns.
    df = df.drop_duplicates(subset=["name", "lat", "lon"])
    logger.info("Gazetteer: %d European places loaded.", len(df))
    return df[["name", "asciiname", "alternatenames", "lat", "lon",
               "country_code", "population"]]


def _load_gazetteer() -> pd.DataFrame:
    """Load the parsed European gazetteer, building the disk cache on first use."""
    path = _cache_path()
    if os.path.exists(path):
        try:
            return pd.read_parquet(path)
        except Exception as e:
            logger.warning("Gazetteer cache unreadable (%s), rebuilding.", e)

    df = _download_gazetteer()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        df.to_parquet(path, index=False)
    except Exception as e:
        logger.warning("Could not write gazetteer cache (%s) — will re-download next time.", e)
    return df


class _PlaceIndex:
    """In-memory name -> place lookup built once from the gazetteer."""

    def __init__(self):
        gaz = _load_gazetteer()
        self.places = gaz.reset_index(drop=True)
        # name(lowercased) -> list of place row indices. Alternate names are
        # many-to-one: e.g. both "München" and "Munich" point at the same row.
        self.name_to_rows: dict[str, list[int]] = {}
        main_names = []
        for i, row in self.places.iterrows():
            for variant in {row["name"], row["asciiname"]}:
                key = str(variant).strip().lower()
                if len(key) >= 2:
                    self.name_to_rows.setdefault(key, []).append(i)
                    main_names.append(key)
            alts = row["alternatenames"]
            if isinstance(alts, str) and alts:
                for alt in alts.split(","):
                    key = alt.strip().lower()
                    if len(key) >= 2:
                        self.name_to_rows.setdefault(key, []).append(i)
            main_names.append(str(row["name"]).strip().lower())
        # Dedupe while preserving order — difflib scans this whole list.
        self.fuzzy_names = list(dict.fromkeys(main_names))
        logger.info("Place index ready: %d places, %d searchable names.",
                    len(self.places), len(self.fuzzy_names))

    def _row_to_result(self, idx: int, allow_small: bool = False) -> dict | None:
        row = self.places.iloc[idx]
        pop = int(row["population"])
        # Tiny hamlets are excluded from *fuzzy* results — a typo hitting a
        # 500-person village is almost never what the user meant. But an
        # exact/prefix match on a village name is legitimate (people who live
        # there search for it), so exact callers pass allow_small=True.
        if pop < 1000 and not allow_small:
            return None
        return {
            "name": str(row["name"]),
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "country_code": str(row["country_code"]),
            "population": pop,
        }

    def search(self, query: str, limit: int = 3) -> list[dict]:
        q = query.strip().lower()
        if len(q) < 2:
            return []

        results: list[dict] = []
        seen_ids: set[int] = set()

        # 1. Exact / prefix hits first (these are what the user typed).
        exact_keys = [q] if q in self.name_to_rows else [
            k for k in self.name_to_rows if k.startswith(q)
        ]
        exact_rows: list[int] = []
        for key in sorted(exact_keys, key=len):  # exact match before longer prefixes
            exact_rows.extend(self.name_to_rows[key])
        for idx in self._rank_rows(exact_rows)[:limit]:
            res = self._row_to_result(idx, allow_small=True)
            if res:
                results.append(res)
                seen_ids.add(idx)

        if len(results) >= limit:
            return results[:limit]

        # 2. Fuzzy matches for typos ("bordeux" -> "bordeaux"). Only consider
        # names within a small edit window of the query length.
        candidates = [n for n in self.fuzzy_names if abs(len(n) - len(q)) <= 2]
        close = difflib.get_close_matches(q, candidates, n=limit * 4, cutoff=0.75)
        fuzzy_rows: list[int] = []
        for name in close:
            fuzzy_rows.extend(self.name_to_rows.get(name, []))
        for idx in self._rank_rows(fuzzy_rows):
            if idx in seen_ids:
                continue
            res = self._row_to_result(idx)
            if res:
                results.append(res)
                seen_ids.add(idx)
            if len(results) >= limit:
                break

        return results[:limit]

    def _rank_rows(self, rows: list[int]) -> list[int]:
        """Dedupe rows, biggest population first."""
        return sorted(set(rows),
                      key=lambda i: int(self.places.iloc[i]["population"]),
                      reverse=True)


_index: _PlaceIndex | None = None


def get_index() -> _PlaceIndex:
    global _index
    if _index is None:
        _index = _PlaceIndex()
    return _index


def search_places(query: str, limit: int = 3) -> list[dict]:
    """Public entry point. Returns [{name, lat, lon, country_code, ...}]."""
    try:
        return get_index().search(query, limit=limit)
    except Exception as e:
        logger.warning("search_places failed: %s", e)
        return []


def nearby_sites(lat: float, lon: float, sites: pd.DataFrame,
                 radius_km: float = 50.0, limit: int = 12) -> pd.DataFrame:
    """Sites within radius_km of (lat, lon), nearest first.

    `sites` is a scorecard frame with latitude/longitude columns.
    """
    if sites.empty:
        return sites
    site_lat = pd.to_numeric(sites["latitude"], errors="coerce")
    site_lon = pd.to_numeric(sites["longitude"], errors="coerce")
    dlat = (site_lat - lat) * np.pi / 180
    dlon = (site_lon - lon) * np.pi / 180
    a = (np.sin(dlat / 2) ** 2
         + np.cos(lat * np.pi / 180) * np.cos(site_lat * np.pi / 180)
         * np.sin(dlon / 2) ** 2)
    dist_km = 6371.0 * 2 * np.arcsin(np.sqrt(a.clip(lower=0)))
    out = sites.assign(_dist_km=dist_km)
    out = out[out["_dist_km"] <= radius_km].sort_values("_dist_km")
    return out.head(limit)
