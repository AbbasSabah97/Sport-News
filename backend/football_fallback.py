"""Unauthenticated scoreboard fallbacks, with no invented fixtures.

ESPN's public endpoints are undocumented and may change. Coverage, particularly
Iraq, can be missing. TheSportsDB's free v1 date endpoint is a second best-effort
source. Use API-Football when an authorized key is configured.
"""
from __future__ import annotations
import concurrent.futures
import datetime as dt
import json
import urllib.parse
from . import collector

LEAGUES={
    "england":"eng.1",
    "spain":"esp.1",
    "ucl":"uefa.champions",
    "worldcup":"fifa.world",
    "asiacup":"afc.asian.cup",
    "euro":"uefa.euro",
    "iraq":"irq.1",
}
IRAQ_WORDS=("iraqi stars","iraqi premier","iraq stars","iraq premier","iraq league")
def parse_espn(data,category,local_date):
    rows=[]
    for event in data.get("events") or []:
        comp=(event.get("competitions") or [{}])[0]
        parties=comp.get("competitors") or []
        home=next((x for x in parties if x.get("homeAway")=="home"),None)
        away=next((x for x in parties if x.get("homeAway")=="away"),None)
        if not home or not away:continue
        kickoff=event.get("date","")
        try:
            date=dt.datetime.fromisoformat(kickoff.replace("Z","+00:00")).astimezone(collector.BAGHDAD).date().isoformat()
            if date!=local_date:continue
        except (TypeError,ValueError):continue
        status=(comp.get("status") or event.get("status") or {}).get("type") or {}
        state=status.get("state","pre")
        abbreviation=status.get("name","SCHEDULED")
        code=("FT" if state=="post" else "LIVE" if state=="in" else "NS")
        if abbreviation=="STATUS_HALFTIME":code="HT"
        if abbreviation=="STATUS_POSTPONED":code="PST"
        if abbreviation=="STATUS_CANCELED":code="CANC"
        def score(x):
            v=x.get("score")
            try:return int(v) if v is not None and state!="pre" else None
            except (ValueError,TypeError):return None
        rows.append(dict(
            id="espn-"+str(event.get("id")),
            competition_id=category,
            league=dict(collector.COMPETITIONS)[category],
            home=(home.get("team") or {}).get("displayName") or "—",
            away=(away.get("team") or {}).get("displayName") or "—",
            home_goals=score(home),away_goals=score(away),
            kickoff=kickoff,status=code,provider="ESPN"))
    return rows

def parse_sportsdb(payload,day):
    result=[]
    for event in payload.get("events") or []:
        name=(event.get("strLeague") or "").lower()
        if not any(word in name for word in IRAQ_WORDS):continue
        date=event.get("dateEvent")
        t=(event.get("strTime") or "00:00:00").split("+")[0]
        try:
            time=dt.datetime.fromisoformat(date+"T"+t.replace("Z",""))
            # SportsDB event times are UTC when supplied as a time.
            instant=time.replace(tzinfo=collector.UTC)
            local=instant.astimezone(collector.BAGHDAD)
            if local.date().isoformat()!=day:continue
        except (ValueError,TypeError):continue
        def score(x):
            try:return int(x) if x is not None and x!="" else None
            except (ValueError,TypeError):return None
        h=score(event.get("intHomeScore"));a=score(event.get("intAwayScore"))
        status="FT" if event.get("strStatus","").lower() in ("match finished","finished") else "NS"
        if h is not None and a is not None: status="FT"
        result.append(dict(
            id="sportsdb-"+str(event.get("idEvent")),
            competition_id="iraq",league=dict(collector.COMPETITIONS)["iraq"],
            home=event.get("strHomeTeam") or "—",
            away=event.get("strAwayTeam") or "—",
            home_goals=h,away_goals=a,
            kickoff=instant.isoformat(),status=status,provider="TheSportsDB"))
    return result

def fetch_espn(args):
    category,slug,day=args
    url=("https://site.api.espn.com/apis/site/v2/sports/soccer/"
         +urllib.parse.quote(slug,safe="")+"/scoreboard?"+urllib.parse.urlencode({"dates":day}))
    return category,json.loads(collector.request(url))

def fallback_fixtures(now):
    day=now.astimezone(collector.BAGHDAD).date().isoformat()
    date=dt.date.fromisoformat(day)
    days={(date-dt.timedelta(days=1)).strftime("%Y%m%d"),date.strftime("%Y%m%d")}
    jobs=[(k,slug,d) for k,slug in LEAGUES.items() for d in sorted(days)]
    output=[];working=set();errors=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures={pool.submit(fetch_espn,job):job for job in jobs}
        for future in concurrent.futures.as_completed(futures):
            try:
                category,payload=future.result()
                working.add(category)
                output+=parse_espn(payload,category,day)
            except (OSError,ValueError,KeyError,TypeError) as exc:
                errors.append(type(exc).__name__)
    if "iraq" not in working or not any(x["competition_id"]=="iraq" for x in output):
        # The free v1 endpoint may return few events or none, depending on coverage.
        for day_to_check in ((date-dt.timedelta(days=1)),date):
            try:
                url="https://www.thesportsdb.com/api/v1/json/123/eventsday.php?"+urllib.parse.urlencode({
                    "d":day_to_check.isoformat(),"s":"Soccer","l":"Iraqi Stars League"})
                data=json.loads(collector.request(url))
                working.add("iraq")
                output+=parse_sportsdb(data,day)
            except (OSError,ValueError,KeyError,TypeError) as exc:
                errors.append("Iraq: "+type(exc).__name__)
    dedup={}
    for row in output:
        if not row.get("home") or row.get("home")=="—":continue
        key=(row["competition_id"],row["home"].casefold(),row["away"].casefold(),row["kickoff"][:13])
        dedup.setdefault(key,row)
    matches=sorted(dedup.values(),key=lambda x:x["kickoff"])
    # "ok" means the feeds responded, not every league necessarily has coverage.
    status="ok" if len(working)==len(LEAGUES) else "partial" if working else "error"
    note=None if status=="ok" else f"تغطية جزئية: تم التحقق من {len(working)} من {len(LEAGUES)} بطولات. بعض المباريات قد لا تتوفر."
    return matches,status,note,sorted(working)
