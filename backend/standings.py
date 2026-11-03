"""Best-effort ESPN league tables. Never infer standings from selected fixtures."""
import concurrent.futures
import json
import os
import urllib.parse
from .collector import request
from .football_fallback import LEAGUES

FIELDS={"points":"points","gamesPlayed":"played","wins":"wins","ties":"draws",
        "losses":"losses","pointDifferential":"goal_difference","goalDifference":"goal_difference",
        "pointsFor":"goals_for","pointsAgainst":"goals_against"}
def entries_from(payload):
    candidates=[]
    def scan(node):
        if isinstance(node,dict):
            a=node.get("entries")
            if isinstance(a,list) and a and isinstance(a[0],dict) and "team" in a[0]:
                candidates.append(a)
            for key in ("standings","children","groups"):
                if key in node:scan(node[key])
        elif isinstance(node,list):
            for n in node:scan(n)
    scan(payload)
    return max(candidates,key=len) if candidates else []

def parse_standings(payload,code):
    result=[]
    for entry in entries_from(payload):
        team=entry.get("team") or {}
        stats={}
        for s in entry.get("stats") or []:
            name=s.get("name") or s.get("abbreviation")
            if name in FIELDS:
                try:stats[FIELDS[name]]=int(float(s["value"]))
                except (TypeError,ValueError,KeyError):pass
        rank=entry.get("rank")
        if rank is None:
            for s in entry.get("stats") or []:
                if s.get("name") in ("rank","playoffSeed"):
                    try:rank=int(float(s.get("value")))
                    except (TypeError,ValueError):pass
        title=team.get("displayName") or team.get("name")
        if not title or "points" not in stats:continue
        result.append({"team":title,"rank":rank if rank is not None else len(result)+1,**stats})
    result.sort(key=lambda x:(int(x.get("rank") or 9999),-x.get("points",0)))
    return result[:30]

def fetch_one(args):
    code,slug=args
    uri="https://site.api.espn.com/apis/v2/sports/soccer/"+urllib.parse.quote(slug,safe="")+"/standings"
    payload=json.loads(request(uri))
    return code,parse_standings(payload,code)


def parse_api_football_standings(data):
    """Convert official API-Football standings without inventing points."""
    out=[]
    league=(data.get("league") or {})
    for table in league.get("standings") or []:
        for item in table:
            team=(item.get("team") or {})
            all_games=(item.get("all") or {})
            if item.get("points") is None or not team.get("name"):continue
            rank=item.get("rank")
            group=item.get("group") or ""
            out.append({
                "team":team["name"],"rank":rank if rank is not None else len(out)+1,
                "points":item["points"],"played":all_games.get("played"),
                "wins":(all_games.get("win")),"draws":all_games.get("draw"),
                "losses":all_games.get("lose"),"goal_difference":item.get("goalsDiff"),
                "group":group,
            })
    return out[:60]

def optional_iraqi_standings():
    """Discover Iraqi league & season; don't assume a league ID."""
    key=os.getenv("API_FOOTBALL_KEY","").strip()
    if not key:return []
    headers={"x-apisports-key":key}
    try:
        leagues=json.loads(request("https://v3.football.api-sports.io/leagues?country=Iraq&current=true",headers))
        candidates=[]
        for candidate in leagues.get("response") or []:
            league=candidate.get("league") or {}
            title=str(league.get("name","")).casefold()
            if any(x in title for x in ("stars league","premier league","iraqi league")):
                seasons=[s for s in candidate.get("seasons") or [] if s.get("current")]
                if seasons:
                    candidates.append((league.get("id"),seasons[0].get("year")))
        for lid,year in candidates[:2]:
            if not lid or not year:continue
            url=("https://v3.football.api-sports.io/standings?league="
                 +str(lid)+"&season="+str(year))
            payload=json.loads(request(url,headers))
            if payload.get("errors"):continue
            for response in payload.get("response") or []:
                data=parse_api_football_standings(response)
                if data:return data
    except (OSError,ValueError,KeyError,TypeError):
        pass
    return []

def get_standings():
    standings={}
    codes=[(k,v) for k,v in LEAGUES.items()]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures=[pool.submit(fetch_one,item) for item in codes]
        for job in concurrent.futures.as_completed(futures):
            try:
                code,rows=job.result()
                if rows:standings[code]=rows
            except (OSError,ValueError,KeyError,TypeError):
                continue
    iraqi=optional_iraqi_standings()
    if iraqi:standings['iraq']=iraqi
    return standings
