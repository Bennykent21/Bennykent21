"""Builds stats.svg from the same contribution calendar your profile shows."""
import datetime as dt
import json
import os
import sys
import urllib.request

LOGIN = os.environ.get("GH_LOGIN", "Bennykent21")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = sys.argv[1] if len(sys.argv) > 1 else "dist/stats.svg"


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
    days = json.load(open(os.environ["FAKE_DAYS"])) if os.environ.get("FAKE_DAYS") else fetch_days()
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w") as f:
        f.write(svg(summarize(days)))
    print(summarize(days))
