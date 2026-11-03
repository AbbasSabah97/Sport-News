"""Optional authorized match events, starting elevens and basic statistics.

Uses only API-Football when API_FOOTBALL_KEY exists on the server.
Never stores keys or returns authentication details in the app's JSON.
"""
import json
import os
import urllib.parse
from .collector import request
LIVE={"1H","HT","2H","ET","BT","P","LIVE"}
STATS=("Ball Possession","Total Shots","Shots on Goal","Shots off Goal",
       "Corner Kicks","Fouls","Yellow Cards","Red Cards","expected_goals")

def parse_details(item):
    events=[]
    for e in (item.get("events") or [])[:60]:
        time=e.get("time") or {}
        minute=time.get("elapsed")
        if minute is None:continue
        extra=time.get("extra")
        clock=str(minute)+("+"+str(extra) if extra else "")
        events.append({
          "minute":clock,
          "team":(e.get("team") or {}).get("name") or "",
          "player":(e.get("player") or {}).get("name") or "",
          "type":e.get("type") or "",
          "detail":e.get("detail") or "",
        })
    stats={}
    allstats=item.get("statistics") or []
    if len(allstats)>=2:
        by_team={str((x.get("team") or {}).get("id")):x for x in allstats}
        teams=item.get("teams") or {}
        home_id=str((teams.get("home") or {}).get("id"))
        away_id=str((teams.get("away") or {}).get("id"))
        home=by_team.get(home_id) or allstats[0]
        away=by_team.get(away_id) or allstats[1]
        def values(block):
            return {x.get("type"):x.get("value") for x in block.get("statistics") or []}
        h,a=values(home),values(away)
        for key in STATS:
            if h.get(key) is None and a.get(key) is None:continue
            stats[key]=str(h.get(key) if h.get(key) is not None else "—")+"  |  "+str(a.get(key) if a.get(key) is not None else "—")
    lineups=[]
    for team in (item.get("lineups") or [])[:2]:
        n=(team.get("team") or {}).get("name") or ""
        form=team.get("formation") or ""
        lineups.append((n+"  "+form).strip())
        for row in (team.get("startXI") or [])[:11]:
            player=(row.get("player") or {}).get("name")
            if player:lineups.append(player)
    return {"events":events[:40],"statistics":stats,"lineups":lineups[:24]}

def enrich(matches):
    key=os.getenv("API_FOOTBALL_KEY","").strip()
    if not key:return matches
    targets=[]
    for row in matches:
        if row.get("status") not in LIVE:continue
        value=row.get("id","")
        if value.startswith("apifootball-") and value.split("-",1)[1].isdigit():
            targets.append(row)
    if not targets:return matches
    targets=targets[:8]
    ids="-".join(x["id"].split("-",1)[1] for x in targets)
    url="https://v3.football.api-sports.io/fixtures?"+urllib.parse.urlencode({"ids":ids})
    try:
        data=json.loads(request(url,{"x-apisports-key":key}))
        if data.get("errors"):return matches
        by_id={str((item.get("fixture") or {}).get("id")):item for item in data.get("response") or []}
        for row in targets:
            item=by_id.get(row["id"].split("-",1)[1])
            if item:row.update(parse_details(item))
    except (OSError,ValueError,TypeError,KeyError):
        pass
    return matches
