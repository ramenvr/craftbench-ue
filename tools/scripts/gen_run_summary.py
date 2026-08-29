#!/usr/bin/env python3
"""Generate a SELF-CONTAINED per-run summary page: ``<run>/summary.html``.

Why this exists: the dashboard's ``web/static/index.html`` is a live SPA (it
fetches ``/api/...`` + opens an EventSource), so opening it standalone just
spins "connecting" forever; and the per-run ``report.html`` pulls Tailwind from
a CDN, so it depends on the network too. This page has ZERO network dependencies
— inline CSS, no CDN, no fetch, no server — so double-clicking the file just
works, offline, forever. The hero image is embedded as a data URI so the page
renders even if the file is moved; the rest of the gallery + the flythrough are
linked relatively (a click away, no network).

Usage:
    python3 tools/scripts/gen_run_summary.py <run-dir> [<run-dir> ...]
    python3 tools/scripts/gen_run_summary.py --all         # every runs/**/summary.json
"""
from __future__ import annotations

import base64
import html
import json
import sys
from pathlib import Path


def _data_uri(p: Path) -> str:
    ext = p.suffix.lower()
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(ext, "application/octet-stream")
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode("ascii")


def _esc(v) -> str:
    return html.escape(str(v))


def _fmt_cost(summ: dict) -> str:
    c = summ.get("est_cost_usd")
    if c is None:
        c = (summ.get("cost_thread") or {}).get("usd")
    if c is None:
        c = (summ.get("cost_snapshot") or {}).get("usd")
    return f"${float(c):.4f}" if c is not None else "—"


def _tools_line(summ: dict) -> str:
    """Best-effort 'by tool' string across run shapes (graded vs drive)."""
    bt = summ.get("by_tool") or (summ.get("verifier") or {}).get("by_tool")
    if isinstance(bt, dict) and bt:
        return ", ".join(f"{k} ×{v}" for k, v in bt.items())
    v = (summ.get("verifier") or {})
    if isinstance(v.get("tools"), list) and v["tools"]:
        return ", ".join(map(str, v["tools"]))
    return "—"


def _rows(summ: dict) -> list[tuple[str, str]]:
    rows = [
        ("verdict", summ.get("verdict", "—")),
        ("model", summ.get("model", "—")),
        ("transport", summ.get("transport", summ.get("mode", "—"))),
        ("cost", _fmt_cost(summ)),
        ("by tool", _tools_line(summ)),
    ]
    agent = summ.get("agent") or {}
    if agent.get("elapsed") is not None:
        rows.append(("agent time", f"{float(agent['elapsed']):.0f}s"))
    if summ.get("project"):
        rows.append(("UE project", summ["project"]))
    sb = summ.get("aura_sandbox") or {}
    if sb.get("active"):
        rows.append(("sandbox persisted", f"{sb.get('persisted', '?')} asset(s)"))
    return [(k, v) for k, v in rows if v not in (None, "", "—") or k in ("verdict", "model")]


def _deliverables(summ: dict) -> list[str]:
    d = summ.get("deliverable") or {}
    out = list(d.get("new") or [])
    out += [f"{p} (changed)" for p in (d.get("changed") or [])]
    return out


_CSS = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { margin:0; font:15px/1.55 -apple-system,Segoe UI,Roboto,sans-serif; background:#0f1420; color:#e6ebf5; }
.wrap { max-width:1100px; margin:0 auto; padding:28px 32px 64px; }
h1 { font-size:22px; margin:0 0 4px; }
.sub { color:#93a1c0; font-size:13px; }
.badge { display:inline-block; font-weight:700; font-size:15px; padding:4px 12px; border-radius:6px; margin:16px 0 8px; }
.ok { background:#14361f; color:#4ade80; } .fail { background:#3a1620; color:#f87171; } .neutral { background:#26304a; color:#b7c3de; }
h2 { font-size:13px; text-transform:uppercase; letter-spacing:.06em; color:#8ea2c8; margin:32px 0 12px; border-bottom:1px solid #26304a; padding-bottom:6px; }
dl { display:grid; grid-template-columns:170px 1fr; gap:2px 16px; font-size:13.5px; margin:0; }
dt { color:#8ea2c8; } dd { margin:0; font-family:ui-monospace,Consolas,monospace; color:#e6ebf5; word-break:break-all; }
.hero img { width:100%; border-radius:8px; display:block; background:#060912; margin-bottom:6px; }
ul.files { list-style:none; padding:0; margin:0; font-family:ui-monospace,Consolas,monospace; font-size:12.5px; }
ul.files li { padding:6px 10px; background:#161d2e; border-radius:5px; margin-bottom:5px; color:#c8d3ea; }
.links a { display:inline-block; margin-right:16px; color:#7db1ff; font-size:13.5px; }
footer { margin-top:44px; color:#5c6a86; font-size:11.5px; }
.empty { color:#7f8fb3; font-size:13px; }
"""


def generate(run_dir: Path) -> Path | None:
    sp = run_dir / "summary.json"
    if not sp.exists():
        return None
    try:
        summ = json.loads(sp.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        summ = {}

    verdict = str(summ.get("verdict", "?"))
    cls = "ok" if verdict in ("PASS", "DRIVE-OK") else ("fail" if "FAIL" in verdict or verdict == "NO_DELIVERABLE" else "neutral")

    # preview bundle (optional) — hero embedded, gallery/video linked relatively.
    sc = run_dir / "preview"
    hero = sc / "stills" / "hero.png"
    hero_html = ""
    if hero.exists():
        hero_html = f'<div class="hero"><img src="{_data_uri(hero)}" alt="generated scene"></div>'

    link_bits = []
    if (sc / "index.html").exists():
        link_bits.append('<a href="preview/index.html">Full preview gallery →</a>')
    if (sc / "flythrough.mp4").exists():
        link_bits.append('<a href="preview/flythrough.mp4">Flythrough video →</a>')
    if (run_dir / "deliverable").is_dir():
        link_bits.append('<a href="deliverable/">Agent deliverable →</a>')
    links_html = f'<div class="links">{" ".join(link_bits)}</div>' if link_bits else ""

    rows_html = "".join(f"<dt>{_esc(k)}</dt><dd>{_esc(v)}</dd>" for k, v in _rows(summ))
    files = _deliverables(summ)
    files_html = ("<ul class='files'>" + "".join(f"<li>{_esc(f)}</li>" for f in files) + "</ul>") \
        if files else "<p class='empty'>No file deliverables recorded.</p>"

    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CraftBench run · {_esc(run_dir.name)}</title>
<style>{_CSS}</style></head>
<body><div class="wrap">
<h1>{_esc(run_dir.name)}</h1>
<div class="sub">CraftBench run summary · self-contained (no server, no network)</div>
<span class="badge {cls}">{_esc(verdict)}</span>
{hero_html}
{links_html}
<h2>Run</h2><dl>{rows_html}</dl>
<h2>Deliverables</h2>{files_html}
<footer>Generated by tools/scripts/gen_run_summary.py · opens offline, no dashboard server needed.</footer>
</div></body></html>"""

    out = run_dir / "summary.html"
    out.write_text(doc, encoding="utf-8")
    return out


def main(argv: list[str]) -> int:
    args = argv[1:]
    if not args:
        print(__doc__)
        return 2
    repo = Path(__file__).resolve().parents[2]
    if args == ["--all"]:
        targets = sorted({p.parent for p in (repo / "runs").rglob("summary.json")})
    else:
        targets = [Path(a) for a in args]
    n = 0
    for t in targets:
        out = generate(t)
        if out:
            print(f"wrote {out}")
            n += 1
        else:
            print(f"skip (no summary.json): {t}", file=sys.stderr)
    return 0 if n else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
