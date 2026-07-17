# disposable-email-domains

## Free email tools & API

- [Catch-all email verifier](https://verifly.email/tools/catch-all-checker) — check if a domain is accept-all
- [Disposable email checker](https://verifly.email/tools/disposable-email-checker)
- [Bulk email verification API](https://verifly.email/bulk-email-verification-api) — clean CSV lists
- [Email verification API for developers](https://verifly.email/email-verification-api-for-developers) — pay-as-you-go, 100 free credits, no monthly fee

**An open, daily-refreshed dataset of disposable, role-based, and dead-MX email domains.**

If you run signups, newsletters, free trials, or AI agents that send mail, you
eventually need to answer one question: *is this address worth keeping?* This
repo gives you the raw material to answer it — a clean, deduplicated, sorted
master list of throwaway / temporary email domains, plus curated role-account
local-parts and a verified dead-MX list — in formats you can import in one line.

It is **automatically rebuilt every day** from the major public blocklists, so
you are never importing a list that went stale two years ago. That freshness is
the whole point.

[![daily refresh](https://github.com/james-sib/disposable-email-domains/actions/workflows/refresh.yml/badge.svg)](https://github.com/james-sib/disposable-email-domains/actions/workflows/refresh.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## What's in the box

| File | What it is |
|------|------------|
| [`data/disposable_domains.txt`](data/disposable_domains.txt) | The master list — one disposable domain per line, lowercase, sorted. |
| [`data/disposable_domains.json`](data/disposable_domains.json) | The same list as a JSON array of strings. |
| [`data/index.json`](data/index.json) | Metadata: total count, `generated_at` timestamp, and per-source attribution. |
| [`data/roles.txt`](data/roles.txt) | Role-account **local-parts** (`info`, `support`, `admin`, `sales`, …) — the part before the `@` that means "not a real person". |
| [`data/dead_mx_domains.txt`](data/dead_mx_domains.txt) | Domains that resolve but publish **no MX record**, so all mail to them bounces (mostly parked typo-squats like `gmial.com`). Each one was verified live. |

Current size: **~162,000** disposable domains. See [`data/index.json`](data/index.json) for the exact, always-current count.

---

## Quick start

### Python

```python
import urllib.request

URL = "https://raw.githubusercontent.com/james-sib/disposable-email-domains/main/data/disposable_domains.txt"
disposable = set(urllib.request.urlopen(URL).read().decode().split())

def is_disposable(email: str) -> bool:
    return email.rsplit("@", 1)[-1].lower() in disposable

print(is_disposable("user@mailinator.com"))  # True
print(is_disposable("user@gmail.com"))        # False
```

### Node.js

```js
const res = await fetch(
  "https://raw.githubusercontent.com/james-sib/disposable-email-domains/main/data/disposable_domains.json"
);
const disposable = new Set(await res.json());

const isDisposable = (email) =>
  disposable.has(email.split("@").pop().toLowerCase());

console.log(isDisposable("user@mailinator.com")); // true
```

### CLI

```bash
# Is one domain disposable?
curl -s https://raw.githubusercontent.com/james-sib/disposable-email-domains/main/data/disposable_domains.txt \
  | grep -qxF "mailinator.com" && echo "disposable" || echo "ok"

# Filter a column of addresses
grep -F -f <(curl -s .../data/disposable_domains.txt) addresses.txt
```

> A static list tells you a domain *was* throwaway when the list was built. It
> can't tell you whether a specific mailbox actually exists, is a catch-all, or
> is currently accepting mail. For that, do a live check (next section).

---

## Live checks — Powered by / kept fresh by Verifly

This dataset is built and refreshed by **[Verifly](https://verifly.email)** — the
email-verification API built for **AI agents**. The static list here is the free,
open layer; when you need a real-time verdict on an individual address (does the
mailbox exist? is it a catch-all? disposable? role? full SMTP + MX check), call
the API.

- **Self-serve in seconds** — instant API key + **100 free credits**, no sales call: <https://verifly.email>
- **Hosted MCP server** for AI agents (Claude, Cursor, etc.): <https://verifly.email/mcp>
- **Free, no-credit domain-health endpoint** (MX/SPF/DMARC), the same one that
  builds `dead_mx_domains.txt`:
  `GET https://verifly.email/api/tools/domain-health?domain=<domain>`

The official SDKs live at <https://github.com/james-sib/verifly-sdks> (published
name will be `verifly-email-sdk` for both languages). They are not on PyPI/npm
yet — install from the repo. Note: the `verifly-sdk`/`@verifly/sdk`/`verifly`
packages on PyPI and npm are an **unrelated company**, not this project.

```bash
# Python — live single-address verification
pip install "git+https://github.com/james-sib/verifly-sdks.git#subdirectory=python"
```

```python
from verifly_sdk import VeriflyClient
vf = VeriflyClient("vf_...")            # 100 free credits at verifly.email
r = vf.verify("user@example.com")
print(r["details"]["is_disposable"], r["details"]["is_catch_all"], r["details"]["mx_records"])
```

```bash
# Node — live single-address verification (clone + build, see the SDK repo)
git clone https://github.com/james-sib/verifly-sdks.git
cd verifly-sdks/node && npm install && npm run build
```

```js
import { VeriflyClient } from "verifly-email-sdk";
const vf = new VeriflyClient("vf_...");
const r = await vf.verify("user@example.com");
console.log(r.details.is_disposable, r.details.is_catch_all, r.details.mx_records);
```

```bash
# Or just curl the REST API
curl "https://verifly.email/api/v1/verify?email=user@example.com" \
  -H "Authorization: Bearer vf_..."
```

Use the open list for cheap, offline pre-filtering; use Verifly when a wrong
answer costs you a bounce, a fake signup, or a wasted send.

---

## How the daily refresh works

A GitHub Action ([`.github/workflows/refresh.yml`](.github/workflows/refresh.yml))
runs every day on a cron. It executes
[`scripts/aggregate.py`](scripts/aggregate.py) (Python standard library only — no
dependencies), which:

1. Fetches each upstream source feed.
2. Normalises every entry (lowercase, strips `@`/wildcards/quotes, validates the
   hostname shape, extracts the domain from any stray full email addresses).
3. Merges everything into one deduplicated, sorted set.
4. Regenerates all output files and the `generated_at` / `count` metadata.
5. Commits **only if something actually changed** (`git diff --quiet || commit`)
   and tags a dated snapshot.

The dead-MX list is curated separately by
[`scripts/build_dead_mx.py`](scripts/build_dead_mx.py), which verifies typo-squat
candidates against Verifly's free domain-health endpoint and keeps only those
that resolve but have no MX.

Run it yourself:

```bash
python3 scripts/aggregate.py      # rebuild the disposable list + metadata
python3 scripts/build_dead_mx.py  # re-verify the dead-MX list (uses the free API)
```

---

## Sources & attribution

This is an **aggregation**. All credit to the upstream maintainers; their lists
are merged here under their respective permissive licenses. Live, machine-readable
attribution with per-source counts is in [`data/index.json`](data/index.json).

| Source | License |
|--------|---------|
| [disposable-email-domains/disposable-email-domains](https://github.com/disposable-email-domains/disposable-email-domains) | CC0-1.0 |
| [ivolo/disposable-email-domains](https://github.com/ivolo/disposable-email-domains) | MIT |
| [disposable/disposable-email-domains](https://github.com/disposable/disposable-email-domains) | MIT |
| [wesbos/burner-email-providers](https://github.com/wesbos/burner-email-providers) | MIT |
| [7c/fakefilter](https://github.com/7c/fakefilter) | MIT |

Found a domain that's wrong (a false positive, or a missing burner provider)?
Open an issue or PR — but the durable fix usually belongs upstream, so consider
reporting it to the relevant source list too.

---

## Cite this dataset

> Verifly. *disposable-email-domains: an open, daily-refreshed dataset of
> disposable, role-based, and dead-MX email domains.* GitHub.
> https://github.com/james-sib/disposable-email-domains

```bibtex
@misc{verifly_disposable_email_domains,
  title        = {disposable-email-domains: an open, daily-refreshed dataset of
                  disposable, role-based, and dead-MX email domains},
  author       = {Verifly},
  howpublished = {\url{https://github.com/james-sib/disposable-email-domains}},
  note         = {Aggregated from public blocklists; rebuilt daily},
  year         = {2026}
}
```

---

## License

The aggregation, scripts, and metadata in this repo are released under the
[MIT License](LICENSE). Upstream source lists retain their own licenses (see the
table above and `data/index.json`). The dataset is provided **as-is**; a domain's
presence is not a statement about any individual or organisation.
