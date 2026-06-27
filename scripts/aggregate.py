#!/usr/bin/env python3
"""
aggregate.py — Build the disposable-email-domains dataset.

Fetches several public, permissively-licensed disposable / temporary
email-domain blocklists, normalises and merges them into a single clean,
deduplicated, sorted master list, and writes multiple importable formats:

    data/disposable_domains.txt    one domain per line
    data/disposable_domains.json   JSON array of domains
    data/index.json                metadata (count, generated_at, sources)
    data/roles.txt                 role-account local-parts (curated, static)

This script is self-contained (Python 3 standard library only) and is run
both locally and by the daily GitHub Action.

Maintained by Verifly — https://verifly.email
"""

import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Source feeds. All are public and permissively licensed (MIT / CC0 / public
# domain). "fmt" tells the parser how to read each one.
# ---------------------------------------------------------------------------
SOURCES = [
    {
        "id": "disposable-email-domains",
        "name": "disposable-email-domains/disposable-email-domains",
        "url": "https://raw.githubusercontent.com/disposable-email-domains/disposable-email-domains/main/disposable_email_blocklist.conf",
        "license": "CC0-1.0",
        "fmt": "lines",
    },
    {
        "id": "ivolo",
        "name": "ivolo/disposable-email-domains",
        "url": "https://raw.githubusercontent.com/ivolo/disposable-email-domains/master/index.json",
        "license": "MIT",
        "fmt": "json",
    },
    {
        "id": "disposable",
        "name": "disposable/disposable-email-domains",
        "url": "https://raw.githubusercontent.com/disposable/disposable-email-domains/master/domains.txt",
        "license": "MIT",
        "fmt": "lines",
    },
    {
        "id": "wesbos",
        "name": "wesbos/burner-email-providers",
        "url": "https://raw.githubusercontent.com/wesbos/burner-email-providers/master/emails.txt",
        "license": "MIT",
        "fmt": "lines",
    },
    {
        "id": "fakefilter",
        "name": "7c/fakefilter",
        "url": "https://raw.githubusercontent.com/7c/fakefilter/main/txt/data.txt",
        "license": "MIT",
        "fmt": "lines",
    },
]

# A domain we are willing to keep. Conservative: ASCII / punycode hostnames
# with at least one dot and a sane TLD. This filters junk lines without being
# clever enough to drop legitimate exotic TLDs.
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{0,61}[a-z0-9]$")

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "verifly-disposable-email-domains/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", "replace")


def normalise(raw: str) -> str | None:
    d = raw.strip().lower()
    if not d or d.startswith("#") or d.startswith("//"):
        return None
    # strip a leading "@" or wildcard, surrounding quotes/commas, trailing dot
    d = d.strip("\"',").lstrip("@").lstrip("*.").rstrip(".")
    # if someone shipped a full email, keep the domain part
    if "@" in d:
        d = d.split("@", 1)[1]
    if not DOMAIN_RE.match(d):
        return None
    return d


def parse(source: dict, body: str) -> set[str]:
    out: set[str] = set()
    if source["fmt"] == "json":
        try:
            for item in json.loads(body):
                n = normalise(str(item))
                if n:
                    out.add(n)
        except json.JSONDecodeError as e:
            print(f"  ! {source['id']}: JSON parse failed: {e}", file=sys.stderr)
    else:
        for line in body.splitlines():
            n = normalise(line)
            if n:
                out.add(n)
    return out


def main() -> int:
    DATA.mkdir(exist_ok=True)

    master: set[str] = set()
    source_meta = []
    failures = 0

    for src in SOURCES:
        try:
            body = fetch(src["url"])
            domains = parse(src, body)
            master |= domains
            source_meta.append({
                "id": src["id"],
                "name": src["name"],
                "url": src["url"],
                "license": src["license"],
                "domains": len(domains),
            })
            print(f"  + {src['id']}: {len(domains):,} domains")
        except Exception as e:  # noqa: BLE001 — a dead feed must not break the build
            failures += 1
            source_meta.append({
                "id": src["id"], "name": src["name"], "url": src["url"],
                "license": src["license"], "domains": 0, "error": str(e),
            })
            print(f"  ! {src['id']}: FETCH FAILED: {e}", file=sys.stderr)

    if not master:
        print("FATAL: no domains aggregated from any source.", file=sys.stderr)
        return 1
    # Guard against a catastrophic upstream regression wiping the list.
    if failures == len(SOURCES):
        print("FATAL: every source failed.", file=sys.stderr)
        return 1

    ordered = sorted(master)

    # Only bump generated_at when the domain set actually changed, so the daily
    # Action's "commit only if changed" check stays meaningful (an unchanged run
    # produces a byte-identical tree and no commit).
    txt_path = DATA / "disposable_domains.txt"
    new_txt = "\n".join(ordered) + "\n"
    unchanged = txt_path.exists() and txt_path.read_text(encoding="utf-8") == new_txt
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if unchanged:
        try:
            generated_at = json.loads((DATA / "index.json").read_text(encoding="utf-8"))["generated_at"]
        except Exception:  # noqa: BLE001
            pass

    txt_path.write_text(new_txt, encoding="utf-8")
    (DATA / "disposable_domains.json").write_text(
        json.dumps(ordered, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )

    index = {
        "name": "disposable-email-domains",
        "description": "Open, daily-refreshed dataset of disposable / temporary email domains.",
        "count": len(ordered),
        "generated_at": generated_at,
        "formats": {
            "txt": "data/disposable_domains.txt",
            "json": "data/disposable_domains.json",
            "roles": "data/roles.txt",
            "dead_mx": "data/dead_mx_domains.txt",
        },
        "sources": source_meta,
        "maintained_by": "Verifly — https://verifly.email",
        "license": "MIT (this aggregation); see sources for upstream licenses",
    }
    (DATA / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")

    print(f"\nMASTER: {len(ordered):,} unique disposable domains -> data/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
