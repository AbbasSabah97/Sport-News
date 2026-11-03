"""Authorized, compact match-center data enrichment for WorldPulse.

No FotMob private endpoints, credentials, or protected content are used.
API-Football is optional and server-only. Injuries and H2H have a persisted
server-side cache so a frequent score refresh does not exhaust API quotas.
"""
from __future__ import annotations
import datetime as dt
import json
import os
from pathlib import Path
import urllib.parse
from .collector import UTC, request

LIVE={"1H","HT","2H","ET","BT","P","LIVE","INT"}
FINISHED={"FT","AET","PEN"}
STATS={
    "Ball Possession":"الاستحواذ","Total Shots":"إجمالي التسديدات",
    "Shots on Goal":"تسديدات على المرمى",
    "Shots off Goal":"تسديدات خارج المرمى",
    "Shots insidebox":"تسديدات داخل المنطقة",
    "Corner Kicks":"الركنيات","Fouls":"الأخطاء",
    "Yellow Cards":"البطاقات الصفراء","Red Cards":"البطاقات الحمراء",
    "Offsides":"التسلل","Total passes":"التمريرات",
    "Passes accurate":"تمريرات ناجحة","expected_goals":"الأهداف المتوقعة (xG)",
}
CACHE_TTL=4*3600
H2H_TTL=24*3600
MAX_DETAILS=8
MAX_EXTRAS=12

def api_json(endpoint,params,key):
    url="https://v3.football.api-sports.io/"+endpoint+"?"+urllib.parse.urlencode(params)
    payload=json.loads(request(url,{"x-apisports-key":key}))
    if payload.get("errors"):raise ValueError("Provider returned an error")
    return payload.get("response") or []

def parse_details(item):
    """Parse the documented multi-fixture payload without making up stats."""
    events=[]
    for e in (item.get("events") or [])[:80]:
        clock=e.get("time") or {}
        elapsed=clock.get("elapsed")
        if elapsed is None:continue
        extra=clock.get("extra")
        minute=str(elapsed)+("+"+str(extra) if extra else "")
        events.append(dict(minute=minute,
            team=(e.get("team") or {}).get("name") or "",
            player=(e.get("player") or {}).get("name") or "",
            assist=(e.get("assist") or {}).get("name") or "",
            type=e.get("type") or "",
            detail=e.get("detail") or ""))

    statistics={}
    statblocks=item.get("statistics") or []
    if len(statblocks)>=2:
        teams=item.get("teams") or {}
        by_team={str((x.get("team") or {}).get("id")):x for x in statblocks}
        home=by_team.get(str((teams.get("home") or {}).get("id"))) or statblocks[0]
        away=by_team.get(str((teams.get("away") or {}).get("id"))) or statblocks[1]
        def take(block):
            return {x.get("type"):x.get("value") for x in block.get("statistics") or []}
        a,b=take(home),take(away)
        for english,arabic in STATS.items():
            if a.get(english) is None and b.get(english) is None:continue
            statistics[arabic]=str(a.get(english) if a.get(english) is not None else "—")+" | "+str(
                b.get(english) if b.get(english) is not None else "—")

    lineup_details=[]
    lineups=[]
    for block in (item.get("lineups") or [])[:2]:
        team=(block.get("team") or {}).get("name") or ""
        formation=block.get("formation") or ""
        coach=(block.get("coach") or {}).get("name") or ""
        def players(key,cap):
            result=[]
            for entry in (block.get(key) or [])[:cap]:
                p=entry.get("player") or {}
                if not p.get("name"):continue
                result.append({k:v for k,v in {
                    "id":p.get("id"),"name":p.get("name"),
                    "number":p.get("number"),"position":p.get("pos"),"grid":p.get("grid")
                }.items() if v is not None})
            return result
        starters=players("startXI",11)
        subs=players("substitutes",16)
        lineup_details.append(dict(team=team,formation=formation,coach=coach,
                                    starters=starters,substitutes=subs))
        lineups.append((team+" "+formation).strip())
        lineups.extend(x["name"] for x in starters)

    player_stats=[]
    for side in (item.get("players") or [])[:2]:
        team=(side.get("team") or {}).get("name") or ""
        for entry in (side.get("players") or [])[:24]:
            info=entry.get("player") or {}
            if not info.get("name"):continue
            st=(entry.get("statistics") or [{}])[0]
            games=st.get("games") or {}
            goals=st.get("goals") or {}
            record={"team":team,"name":info["name"],"number":info.get("number"),
                    "position":games.get("position"),"minutes":games.get("minutes"),
                    "rating":games.get("rating"),"goals":goals.get("total"),
                    "assists":goals.get("assists")}
            player_stats.append({k:v for k,v in record.items() if v is not None})

    fixture=item.get("fixture") or {}
    venue=fixture.get("venue") or {}
    league=item.get("league") or {}
    metadata={k:v for k,v in {
        "venue":venue.get("name"),"city":venue.get("city"),
        "referee":fixture.get("referee"),"round":league.get("round"),
    }.items() if v}
    result=dict(events=events[:50],statistics=statistics,lineups=lineups[:26],
                lineup_details=lineup_details,player_stats=player_stats[:40])
    result.update(metadata)
    return result

def parse_injuries(data):
    """API-Football injuries: Missing Fixture vs Questionable, not all are injured."""
    out={}
    for item in data[:100]:
        fixture=str((item.get("fixture") or {}).get("id") or "")
        p=item.get("player") or {}
        if not fixture or not p.get("name"):continue
        team=(item.get("team") or {}).get("name") or ""
        out.setdefault(fixture,[])
        out[fixture].append({
            "team":team,"player":p["name"],
            "status":item.get("type") or "غير محدد",
            "reason":item.get("reason") or "السبب غير محدد",
        })
    return {k:v[:28] for k,v in out.items()}

def parse_h2h(items):
    out=[]
    for event in items[:8]:
        t=event.get("teams") or {}
        h=(t.get("home") or {}).get("name")
        a=(t.get("away") or {}).get("name")
        goals=event.get("goals") or {}
        fixture=event.get("fixture") or {}
        if not h or not a or not fixture.get("date"):continue
        out.append(dict(home=h,away=a,date=fixture["date"],
            home_goals=goals.get("home"),away_goals=goals.get("away")))
    return out[:5]

def load_cache(path):
    try:
        data=json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data,dict) else {}
    except (OSError,ValueError,TypeError):return {}

def enrich(matches,now=None,cache_path="docs/match-extras-cache.json"):
    """Return (enriched matches, cache); make no paid request without a key."""
    now=now or dt.datetime.now(UTC)
    key=os.getenv("API_FOOTBALL_KEY","").strip()
    cache=load_cache(cache_path)
    if not key:return matches,cache
    t=now.timestamp()
    targets=[]
    for row in matches:
        value=str(row.get("id",""))
        if not value.startswith("apifootball-") or not value.split("-",1)[1].isdigit():continue
        try:delta=(dt.datetime.fromisoformat(row["kickoff"].replace("Z","+00:00"))-now).total_seconds()
        except (ValueError,KeyError,TypeError):continue
        if row.get("status") in LIVE|FINISHED or (-3*3600<=delta<=3*3600):
            targets.append(row)
    targets=targets[:MAX_DETAILS]
    if not targets:return matches,cache

    ids=[x["id"].split("-",1)[1] for x in targets]
    try:
        response=api_json("fixtures",{"ids":"-".join(ids)},key)
        records={str((p.get("fixture") or {}).get("id")):p for p in response}
        for row in targets:
            item=records.get(row["id"].split("-",1)[1])
            if item:
                row.update(parse_details(item))
                # Preserve latest state from authoritative detail response.
                f=item.get("fixture") or {}
                if (f.get("status") or {}).get("short"):
                    row["status"]=f["status"]["short"]
                score=item.get("goals") or {}
                if score.get("home") is not None:row["home_goals"]=score["home"]
                if score.get("away") is not None:row["away_goals"]=score["away"]
    except (OSError,ValueError,TypeError,KeyError):pass

    # Cached extras only for current fixture ids. A separate refresh every
    # four hours is supported without repeated API calls every five minutes.
    extra_ids=ids[:MAX_EXTRAS]
    injuries=cache.get("injuries") or {}
    if t-float(cache.get("injuries_checked",0))>=CACHE_TTL:
        try:
            response=api_json("injuries",{"ids":"-".join(extra_ids)},key)
            parsed=parse_injuries(response)
            injuries.update(parsed)
            cache["injuries"]=injuries
            cache["injuries_checked"]=t
        except (OSError,ValueError,TypeError,KeyError):pass

    headtohead=cache.get("headtohead") or {}
    checked=cache.get("h2h_checked") or {}
    # Bound the head-to-head calls and store results once per 24 hours.
    fetched=0
    for row in targets:
        fid=row["id"].split("-",1)[1]
        if t-float(checked.get(fid,0))<H2H_TTL:continue
        # Extract real team ids from authorized current fixture detail.
        h=row.get("home_id");a=row.get("away_id")
        if not (str(h).isdigit() and str(a).isdigit()):continue
        if fetched>=2:break
        try:
            response=api_json("fixtures/headtohead",
                {"h2h":str(h)+"-"+str(a),"last":5},key)
            headtohead[fid]=parse_h2h(response)
            checked[fid]=t
            fetched+=1
        except (OSError,ValueError,TypeError,KeyError):continue
    cache["headtohead"]=headtohead
    cache["h2h_checked"]=checked

    for row in targets:
        fid=row["id"].split("-",1)[1]
        if fid in injuries:row["injuries"]=injuries[fid]
        if fid in headtohead:row["headtohead"]=headtohead[fid]
    # Compact the cache to current fixtures and don't retain player data forever.
    current=set(ids)
    for field in ("injuries","headtohead","h2h_checked"):
        cache[field]={k:v for k,v in (cache.get(field) or {}).items() if k in current}
    return matches,cache
