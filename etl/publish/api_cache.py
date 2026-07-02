"""Publish API cache items during ETL publish."""
from __future__ import annotations

from atwc26_core.api_cache import builders, keys
from atwc26_core.api_cache.store import ApiCacheStore, get_api_cache_store
from atwc26_core.data import DataStore, get_store


def publish_api_cache(manifest: dict, *, store: DataStore | None = None) -> dict[str, int]:
    """Materialize API-ready cache items. Returns counts of written/skipped keys."""
    store = store or get_store()
    cache = get_api_cache_store()
    pk = keys.dataset_pk(manifest.get("dataset", "wc26"))
    written = 0
    skipped = 0

    def _upsert(sk: str, payload, source_sha: str, sources: list[str]) -> None:
        nonlocal written, skipped
        if not source_sha:
            return
        if cache.should_skip(pk, sk, source_sha):
            skipped += 1
            return
        cache.put_item(
            pk=pk,
            sk=sk,
            payload=payload,
            source_sha256=source_sha,
            source_artifacts=sources,
        )
        written += 1

    payload, sha, sources = builders.build_standings(store, manifest)
    _upsert(keys.standings_sk(), payload, sha, sources)

    overview, osha, osources = builders.build_overview(store, manifest)
    _upsert(keys.overview_sk(), overview, osha, osources)

    wpayload, wsha, wsources = builders.build_winner_probabilities(store, manifest)
    if wpayload is not None:
        _upsert(keys.winner_probabilities_sk(), wpayload, wsha, wsources)

    bracket, bsha, bsources = builders.build_bracket(store, manifest)
    _upsert(keys.bracket_sk(), bracket, bsha, bsources)

    return {"written": written, "skipped": skipped}


def publish_teams_cache(manifest: dict, *, store: DataStore | None = None) -> dict[str, int]:
    store = store or get_store()
    cache = get_api_cache_store()
    pk = keys.dataset_pk(manifest.get("dataset", "wc26"))
    written = 0
    skipped = 0

    payload, sha, sources = builders.build_teams(store, manifest)
    if not cache.should_skip(pk, keys.teams_sk(), sha):
        cache.put_item(pk=pk, sk=keys.teams_sk(), payload=payload, source_sha256=sha, source_artifacts=sources)
        written += 1
    else:
        skipped += 1

    for team_name in store.teams["team_name"].unique():
        tpayload, tsha, tsources = builders.build_team_players(store, team_name, manifest)
        if tpayload is None:
            continue
        sk = keys.team_players_sk(team_name)
        if cache.should_skip(pk, sk, tsha):
            skipped += 1
            continue
        cache.put_item(pk=pk, sk=sk, payload=tpayload, source_sha256=tsha, source_artifacts=tsources)
        written += 1

    return {"written": written, "skipped": skipped}


def publish_matches_cache(manifest: dict, *, store: DataStore | None = None) -> dict[str, int]:
    store = store or get_store()
    cache = get_api_cache_store()
    pk = keys.dataset_pk(manifest.get("dataset", "wc26"))
    written = 0
    skipped = 0

    payload, sha, sources = builders.build_matches(store, manifest)
    if not cache.should_skip(pk, keys.matches_sk(), sha):
        cache.put_item(pk=pk, sk=keys.matches_sk(), payload=payload, source_sha256=sha, source_artifacts=sources)
        written += 1
    else:
        skipped += 1

    for match in store.matches:
        gid = str(match["game_id"])
        mpayload, msha, msources = builders.build_match_detail(store, gid, manifest)
        if mpayload is None:
            continue
        sk = keys.match_detail_sk(gid)
        if cache.should_skip(pk, sk, msha):
            skipped += 1
            continue
        cache.put_item(pk=pk, sk=sk, payload=mpayload, source_sha256=msha, source_artifacts=msources)
        written += 1

    for player_id in store.players["player_id"].unique():
        ppayload, psha, psources = builders.build_player_detail(store, int(player_id), manifest)
        if ppayload is None:
            continue
        sk = keys.player_detail_sk(player_id)
        if cache.should_skip(pk, sk, psha):
            skipped += 1
            continue
        cache.put_item(pk=pk, sk=sk, payload=ppayload, source_sha256=psha, source_artifacts=psources)
        written += 1

    return {"written": written, "skipped": skipped}
