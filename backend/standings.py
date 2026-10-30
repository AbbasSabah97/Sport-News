"""Best-effort ESPN league tables. Never infer standings from selected fixtures."""
import concurrent.futures
import json
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
    return standings
