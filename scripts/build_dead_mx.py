#!/usr/bin/env python3
"""
build_dead_mx.py — curate a small, VERIFIED list of dead-MX email domains.

A "dead-MX" domain is one that IS registered (resolves in DNS) but publishes
NO MX records, so any mail addressed to it bounces. The classic examples are
typo-squats of popular mail providers (gmial.com, hotmial.com, ...) that are
parked. Filtering these at signup time prevents guaranteed-bounce addresses.

We verify every candidate against Verifly's FREE domain-health endpoint and
keep only those that resolve but have an empty MX set. API use is modest:
a few hundred lookups against a free, unauthenticated endpoint.

Run manually / occasionally — the daily Action does NOT re-verify these
(to keep the cron fast and avoid hammering the endpoint); the curated result
is committed to the repo.
"""

import json
import sys
import time
import urllib.request
from pathlib import Path

ENDPOINT = "https://verifly.email/api/tools/domain-health?domain="
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "dead_mx_domains.txt"
CANDIDATES = Path(__file__).resolve().parent / "dead_mx_candidates.txt"


def check(domain: str):
    """Return (resolves, has_mx) or None on error."""
    try:
        req = urllib.request.Request(
            ENDPOINT + domain,
            headers={"User-Agent": "verifly-disposable-email-domains/1.0"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        mx = data.get("mx") or []
        root_err = (data.get("txtLookup") or {}).get("rootError", "")
        resolves = root_err != "ENOTFOUND"
        return resolves, len(mx) > 0
    except Exception as e:  # noqa: BLE001
        print(f"  ! {domain}: {e}", file=sys.stderr)
        return None


def main() -> int:
    candidates = [
        c.strip().lower()
        for c in CANDIDATES.read_text(encoding="utf-8").splitlines()
        if c.strip() and not c.startswith("#")
    ]
    candidates = sorted(set(candidates))
    print(f"Verifying {len(candidates)} candidates via free domain-health endpoint...")

    dead = []
    for d in candidates:
        res = check(d)
        if res is None:
            continue
        resolves, has_mx = res
        if resolves and not has_mx:
            dead.append(d)
            print(f"  DEAD-MX: {d}")
        time.sleep(0.15)  # be polite to the free endpoint

    dead = sorted(set(dead))
    header = (
        "# Dead-MX email domains: registered domains that publish NO MX record,\n"
        "# so all mail to them bounces. Mostly parked typo-squats of popular mail\n"
        "# providers. Each entry was verified via Verifly's free domain-health API.\n"
        "# Verify live: https://verifly.email/api/tools/domain-health?domain=<d>\n"
        "#\n"
        "# Maintained by Verifly — https://verifly.email\n"
    )
    OUT.write_text(header + "\n".join(dead) + ("\n" if dead else ""), encoding="utf-8")
    print(f"\nWrote {len(dead)} verified dead-MX domains -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
