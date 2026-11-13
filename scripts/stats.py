"""Builds stats.svg from the same contribution calendar your profile shows."""
import datetime as dt
import json
import os
import sys
import urllib.request

LOGIN = os.environ.get("GH_LOGIN", "Bennykent21")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else "dist"


COLORS = {
    "Kotlin": "#A97BFF", "Dart": "#00B4AB", "TypeScript": "#3178C6", "JavaScript": "#F1E05A",
    "Python": "#3572A5", "CSS": "#663399", "HTML": "#E34C26", "PLpgSQL": "#336790",
    "Java": "#B07219", "Shell": "#89E051", "Swift": "#F05138", "Go": "#00ADD8",
}


def rest(path):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={"Authorization": f"bearer {TOKEN}", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def fetch_langs():
    totals = {}
    for repo in rest(f"/users/{LOGIN}/repos?per_page=100&type=owner"):
        if repo["fork"] or repo["archived"]:
            continue
        for lang, size in rest(f"/repos/{LOGIN}/{repo['name']}/languages").items():
            totals[lang] = totals.get(lang, 0) + size
    return totals


def langs_svg(totals, top=6):
    items = sorted(totals.items(), key=lambda kv: -kv[1])
    total = sum(totals.values()) or 1
    shown = items[:top]
    other = sum(v for _, v in items[top:])
    if other:
        shown.append(("Other", other))
    w, h, pad = 800, 128, 24
    bar_w = w - 2 * pad
    x, bars, legend = pad, [], []
    for i, (lang, size) in enumerate(shown):
        frac = size / total
        color = COLORS.get(lang, "#8b949e")
        seg = max(bar_w * frac, 2)
        bars.append(f'<rect x="{x:.1f}" y="50" width="{seg:.1f}" height="12" fill="{color}"/>')
        x += seg
        col, row = i % 4, i // 4
        lx, ly = pad + col * (bar_w / 4), 88 + row * 24
        legend.append(f'<circle cx="{lx+5:.1f}" cy="{ly-4}" r="5" fill="{color}"/>'
                      f'<text x="{lx+16:.1f}" y="{ly}" class="lbl">{lang} <tspan class="pct">{frac*100:.1f}%</tspan></text>')
    h = 88 + ((len(shown) - 1) // 4) * 24 + 22
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="Most used languages">
<style>
  .bg{{fill:#ffffff;stroke:#d0d7de}} .ttl{{fill:#1f2328;font:600 15px 'Segoe UI',Ubuntu,sans-serif}}
  .lbl{{fill:#1f2328;font:400 13px 'Segoe UI',Ubuntu,sans-serif}} .pct{{fill:#57606a}}
  @media (prefers-color-scheme: dark) {{
    .bg{{fill:#0d1117;stroke:#30363d}} .ttl{{fill:#e6edf3}} .lbl{{fill:#e6edf3}} .pct{{fill:#8b949e}}
  }}
</style>
<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="10" class="bg"/>
<text x="{pad}" y="34" class="ttl">Most used languages</text>
<clipPath id="r"><rect x="{pad}" y="50" width="{bar_w}" height="12" rx="6"/></clipPath>
<g clip-path="url(#r)">{"".join(bars)}</g>
{"".join(legend)}
</svg>'''


def gql(query, **variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit(body["errors"])
    return body["data"]


def fetch_days():
    created = gql("query($l:String!){user(login:$l){createdAt}}", l=LOGIN)["user"]["createdAt"]
    now = dt.datetime.now(dt.timezone.utc)
    days = {}
    for year in range(int(created[:4]), now.year + 1):
        start = dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc)
        end = min(dt.datetime(year, 12, 31, 23, 59, 59, tzinfo=dt.timezone.utc), now)
        data = gql(
            """query($l:String!,$f:DateTime!,$t:DateTime!){user(login:$l){
               contributionsCollection(from:$f,to:$t){contributionCalendar{
               weeks{contributionDays{date contributionCount}}}}}}""",
            l=LOGIN, f=start.isoformat(), t=end.isoformat(),
        )
        cal = data["user"]["contributionsCollection"]["contributionCalendar"]
        for w in cal["weeks"]:
            for d in w["contributionDays"]:
                days[d["date"]] = d["contributionCount"]
    return dict(sorted(days.items()))


def summarize(days):
    today = dt.date.today()
    dates = [dt.date.fromisoformat(d) for d in days if dt.date.fromisoformat(d) <= today]
    counts = {dt.date.fromisoformat(k): v for k, v in days.items()}
    total = sum(counts[d] for d in dates)
    this_year = sum(counts[d] for d in dates if d.year == today.year)
    longest = run = 0
    for d in dates:
        run = run + 1 if counts[d] > 0 else 0
        longest = max(longest, run)
    # The current streak survives a day with nothing yet today.
    cur, d = 0, today if counts.get(today, 0) > 0 else today - dt.timedelta(days=1)
    while counts.get(d, 0) > 0:
        cur += 1
        d -= dt.timedelta(days=1)
    best_day = max(dates, key=lambda x: counts[x]) if dates else today
    return {
        "total": total, "year": this_year, "current": cur, "longest": longest,
        "best": counts.get(best_day, 0), "since": dates[0].year if dates else today.year,
        "updated": today.strftime("%d %b %Y"),
    }


def svg(s):
    tiles = [
        (f"{s['total']:,}", f"Contributions since {s['since']}"),
        (f"{s['year']:,}", f"Contributions in {dt.date.today().year}"),
        (f"{s['current']}", "Current streak (days)"),
        (f"{s['longest']}", "Longest streak (days)"),
    ]
    w, h, tw = 800, 150, 200
    parts = []
    for i, (num, label) in enumerate(tiles):
        x = i * tw + tw / 2
        parts.append(f'<text x="{x}" y="72" class="num">{num}</text>')
        parts.append(f'<text x="{x}" y="102" class="lbl">{label}</text>')
        if i:
            parts.append(f'<line x1="{i*tw}" y1="40" x2="{i*tw}" y2="112" class="sep"/>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="GitHub contribution stats">
<style>
  .bg{{fill:#ffffff;stroke:#d0d7de}} .num{{fill:#0969da;font:700 30px 'Segoe UI',Ubuntu,sans-serif;text-anchor:middle}}
  .lbl{{fill:#57606a;font:400 13px 'Segoe UI',Ubuntu,sans-serif;text-anchor:middle}} .sep{{stroke:#d0d7de}}
  .foot{{fill:#8c959f;font:400 11px 'Segoe UI',Ubuntu,sans-serif;text-anchor:middle}}
  @media (prefers-color-scheme: dark) {{
    .bg{{fill:#0d1117;stroke:#30363d}} .num{{fill:#58a6ff}} .lbl{{fill:#8b949e}} .sep{{stroke:#30363d}} .foot{{fill:#6e7681}}
  }}
</style>
<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="10" class="bg"/>
{chr(10).join(parts)}
<text x="{w/2}" y="136" class="foot">Best day: {s['best']} contributions · Updated {s['updated']}</text>
</svg>'''


if __name__ == "__main__":
    fake = os.environ.get("FAKE_DAYS")
    days = json.load(open(fake)) if fake else fetch_days()
    langs = json.load(open(os.environ["FAKE_LANGS"])) if fake else fetch_langs()
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "stats.svg"), "w") as f:
        f.write(svg(summarize(days)))
    with open(os.path.join(OUT_DIR, "langs.svg"), "w") as f:
        f.write(langs_svg(langs))
    print(summarize(days), sorted(langs.items(), key=lambda kv: -kv[1])[:6])
