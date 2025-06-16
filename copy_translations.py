#!/usr/bin/env python3
"""
Clone theme‑specific translations (JSON templates, section groups, shared data
sections, locale content) from a **source** theme to a **destination** theme.

Logging flags
─────────────
--verbose     → one line per resource (counts)
--show-keys   → list *every* key/value copied (implies --verbose)
--timing      → shows elapsed time per locale
--dry-run     → simulate without writing
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from itertools import islice
from typing import Dict, Generator, Iterable, List

import requests

API_VERSION = "2025-04"
MAX_IDS_PER_QUERY = 250
MAX_TRANSLATIONS_PER_MUT = 100

RESOURCE_TYPES = [
    "ONLINE_STORE_THEME",
    "ONLINE_STORE_THEME_SECTION_GROUP",
    "ONLINE_STORE_THEME_JSON_TEMPLATE",
    "ONLINE_STORE_THEME_SETTINGS_DATA_SECTIONS",
    "ONLINE_STORE_THEME_LOCALE_CONTENT",
]

# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def chunked(it: Iterable, size: int) -> Generator[list, None, None]:
    itr = iter(it)
    while (batch := list(islice(itr, size))):
        yield batch


def short_gid(gid: str) -> str:
    return gid.split("/")[-1]


def graphql(shop: str, token: str, query: str, variables: dict | None = None):
    url = f"https://{shop}/admin/api/{API_VERSION}/graphql.json"
    headers = {"Content-Type": "application/json", "X-Shopify-Access-Token": token}
    r = requests.post(url, headers=headers, json={"query": query, "variables": variables or {}})
    r.raise_for_status()
    data = r.json()
    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"], indent=2))
    return data["data"]

# ──────────────────────────────────────────────────────────────
# Discovery helpers
# ──────────────────────────────────────────────────────────────

def shop_locales(shop: str, token: str) -> List[str]:
    q = "query{ shopLocales{ locale } }"
    return [l["locale"] for l in graphql(shop, token, q)["shopLocales"]]


def list_resources(shop: str, token: str, rtype: str, theme_id: int) -> List[dict]:
    out, cursor = [], None
    snippet = f"/{theme_id}"
    q = (
        "query($f:Int!,$a:String,$t:TranslatableResourceType!){"
        "translatableResources(first:$f,after:$a,resourceType:$t){pageInfo{hasNextPage endCursor}edges{node{resourceId translatableContent{key digest}}}}}"
    )
    while True:
        conn = graphql(shop, token, q, {"f": 100, "a": cursor, "t": rtype})["translatableResources"]
        for e in conn["edges"]:
            n = e["node"]
            if snippet in n["resourceId"]:
                out.append(n)
        if conn["pageInfo"]["hasNextPage"]:
            cursor = conn["pageInfo"]["endCursor"]
        else:
            break
    return out

# ──────────────────────────────────────────────────────────────
# Bulk fetch + register
# ──────────────────────────────────────────────────────────────

def fetch_locale_bulk(shop: str, token: str, ids: List[str], locale: str) -> Dict[str, List[dict]]:
    out: Dict[str, List[dict]] = {}
    query = (
        "query($ids:[ID!]!,$loc:String!,$first:Int!){"
        "translatableResourcesByIds(resourceIds:$ids, first:$first){edges{node{resourceId translations(locale:$loc){key value}}}}}"
    )
    for batch in chunked(ids, MAX_IDS_PER_QUERY):
        data = graphql(shop, token, query, {"ids": batch, "loc": locale, "first": len(batch)})
        for edge in data["translatableResourcesByIds"]["edges"]:
            node = edge["node"]
            out[node["resourceId"]] = node["translations"]
    return out


def register_bulk(shop: str, token: str, rid: str, inputs: List[dict], dry: bool):
    if dry or not inputs:
        return []
    mutation = (
        "mutation($id:ID!,$trs:[TranslationInput!]!){"
        "translationsRegister(resourceId:$id,translations:$trs){userErrors{message field}}}"
    )
    errs = []
    for batch in chunked(inputs, MAX_TRANSLATIONS_PER_MUT):
        res = graphql(shop, token, mutation, {"id": rid, "trs": batch})["translationsRegister"]
        errs.extend(res["userErrors"])
    return errs

# ──────────────────────────────────────────────────────────────
# Main CLI
# ──────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shop", required=True)
    ap.add_argument("--source-theme-id", type=int, required=True)
    ap.add_argument("--dest-theme-id", type=int, required=True)
    ap.add_argument("--token")
    ap.add_argument("--locales", help="csv list (default all)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--show-keys", action="store_true")
    ap.add_argument("--timing", action="store_true", help="Live and summary timing")
    args = ap.parse_args()

    if args.show_keys:
        args.verbose = True

    token = args.token or os.getenv("SHOPIFY_ADMIN_TOKEN")
    if not token:
        sys.exit("No Admin API token provided.")

    locales = [l.strip() for l in args.locales.split(",")] if args.locales else shop_locales(args.shop, token)
    print("Locales:", ", ".join(locales))

    locale_time: Dict[str, float] = {loc: 0.0 for loc in locales}

    for rt in RESOURCE_TYPES:
        print(f"\n▶ {rt} …")
        resources = list_resources(args.shop, token, rt, args.source_theme_id)
        if not resources:
            print("  (none)")
            continue

        digest_map = {n["resourceId"]: {c["key"]: c["digest"] for c in n["translatableContent"]} for n in resources}
        ids = [n["resourceId"] for n in resources]

        for loc in locales:
            start = time.perf_counter()
            print(f"  • {loc}")
            sys.stdout.flush()
            trans_by_res = fetch_locale_bulk(args.shop, token, ids, loc)
            processed = 0
            for src_id, translations in trans_by_res.items():
                dest_id = src_id.replace(f"/{args.source_theme_id}", f"/{args.dest_theme_id}", 1)
                inputs = [
                    {
                        "key": t["key"],
                        "locale": loc,
                        "value": t["value"],
                        "translatableContentDigest": digest_map[src_id].get(t["key"]),
                    }
                    for t in translations if digest_map[src_id].get(t["key"]) and t["value"] is not None
                ]
                if args.show_keys and inputs:
                    for inp in inputs:
                        print(f"     · {short_gid(dest_id)} || {inp['key']}: {inp['value'][:60]!r}")
                elif args.verbose:
                    print(f"     ↳ {short_gid(dest_id)} ({len(inputs)} keys){' [DRY]' if args.dry_run else ''}")
                if not args.dry_run:
                    register_bulk(args.shop, token, dest_id, inputs, args.dry_run)
                processed += 1
                if args.timing and not args.verbose and processed % 10 == 0:
                    elapsed = time.perf_counter() - start
                    sys.stdout.write(f"     … {processed}/{len(trans_by_res)} resources processed ({elapsed:.1f}s elapsed)\r")
                    sys.stdout.flush()
            if args.timing and not args.verbose:
                sys.stdout.write(" " * 80 + "\r")  # clear line
                sys.stdout.flush()
            locale_time[loc] += time.perf_counter() - start

    if args.timing:
        print("\nTiming per locale:")
        for loc, secs in locale_time.items():
            print(f"  {loc}: {secs:.2f}s")

    print("\n✓ Done")


if __name__ == "__main__":
    main()
