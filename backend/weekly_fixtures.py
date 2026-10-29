"""Upcoming seven Baghdad-local calendar dates, never inferred from device time.

ESPN month requests are unofficial and may return partial league coverage.
Iraq's verified 2026-10-30 round-12 schedule is a short-lived fallback only,
not a replacement for a licensed continuously updated feed.
"""
from __future__ import annotations

import concurrent.futures
import datetime as dt
import json
import os
import urllib.parse
from . import collector
from .football_fallback import LEAGUES, parse_espn, parse_sportsdb

WINDOW_DAYS = 7
VERIFIED_DATE = dt.date(2026,10,30)
IRAQ_SOURCE = "https://iraqstarsleague.com/en/matches?league_id=1&round=12"
# Verified from Iraq Stars League's matchday 12 page as of 2026-10-30.
# Listed site times are UTC; local display converts to Baghdad (+03:00).
# Only future events are used. The static entries expire automatically.
VERIFIED_IRAQ = [
    ("2026-10-30T14:00:00+00:00","الكرمة","دهوك"),
    ("2026-10-30T14:45:00+00:00","كربلاء","الطلبة"),
    ("2026-10-30T16:00:00+00:00","الكرخ","الغراف"),
    ("2026-10-30T16:30:00+00:00","أربيل","غاز الشمال"),
    ("2026-10-31T13:30:00+00:00","نفط ميسان","زاخو"),
    ("2026-10-31T14:00:00+00:00","الزوراء","ديالى"),
    ("2026-10-31T16:30:00+00:00","الشرطة","نوروز"),
]

def local_day(stamp):
    return dt.datetime.fromisoformat(stamp.replace("Z","+00:00")).astimezone(collector.BAGHDAD).date()

def week_window(now):
    begin=now.astimezone(collector.BAGHDAD).date()
    return begin,begin+dt.timedelta(days=WINDOW_DAYS-1)

def official_iraq_snapshot(now):
    start,end=week_window(now)
    # Not valid as a live feed after the verified snapshot period.
    if start<VERIFIED_DATE or start>dt.date(2026,10,31):
        return []
    rows=[]
    for stamp,home,away in VERIFIED_IRAQ:
        date=local_day(stamp)
        if start<=date<=end and dt.datetime.fromisoformat(stamp)>now:
            rows.append(dict(id="iraq-official-"+stamp[:10]+home,competition_id="iraq",
                league="الدوري العراقي",home=home,away=away,home_goals=None,
                away_goals=None,kickoff=stamp,status="NS",
                provider="دوري نجوم العراق (جدول مؤكد بتاريخ 30 أكتوبر)",
                source_url=IRAQ_SOURCE,
                schedule_verified_at="2026-10-30"))
    return rows

def fetch_espn_month(job):
    code,slug,month=job
    uri=("https://site.api.espn.com/apis/site/v2/sports/soccer/"
         +urllib.parse.quote(slug,safe="")+"/scoreboard?"
         +urllib.parse.urlencode({"dates":month,"limit":500}))
    return code,json.loads(collector.request(uri))

def monthly_tasks(begin,end):
    # Include previous UTC month for matches just after midnight in Baghdad.
    start_utc=begin-dt.timedelta(days=1)
    months={}
    cursor=dt.date(start_utc.year,start_utc.month,1)
    while cursor<=end:
        months[cursor.strftime("%Y%m")]=True
        cursor=(cursor.replace(day=28)+dt.timedelta(days=4)).replace(day=1)
    return [(code,slug,m) for code,slug in LEAGUES.items() for m in months]

def within_week(rows,begin,end):
    out=[]
    for row in rows:
        try:
            date=local_day(row["kickoff"])
            if begin<=date<=end:out.append(row)
        except (KeyError,TypeError,ValueError):pass
    return out

def merge_matches(rows):
    """Deterministically prefer trusted scheduled rows, avoid duplicating teams."""
    priority={"API-Football":0,"دوري نجوم العراق (جدول مؤكد بتاريخ 30 أكتوبر)":1,"TheSportsDB":2,"ESPN":3}
    dedup={}
    for match in sorted(rows,key=lambda x:priority.get(x.get("provider"),5)):
        if match.get("home") in (None,"—") or match.get("away") in (None,"—"):continue
        # Provider IDs are different; canonical team names are not guaranteed.
        key=(match["competition_id"],match["home"].casefold(),
             match["away"].casefold(),local_day(match["kickoff"]).isoformat())
        dedup.setdefault(key,match)
    return sorted(dedup.values(),key=lambda x:(x["kickoff"],x["competition_id"],x["home"]))

def fallback_week(now):
    begin,end=week_window(now)
    results=[];responded=set()
    jobs=monthly_tasks(begin,end)
    with concurrent.futures.ThreadPoolExecutor(max_workers=7) as pool:
        futures={pool.submit(fetch_espn_month,job):job for job in jobs}
        for future in concurrent.futures.as_completed(futures):
            try:
                code,payload=future.result()
                if not isinstance(payload.get("events"),list):continue
                responded.add(code)
                # parse_espn expects a single date so provide each real event day.
                # Filter by the Baghdad-local dates in the week.
                for event in payload["events"]:
                    try:
                        date=local_day(event["date"]).isoformat()
                        results.extend(parse_espn({"events":[event]},code,date))
                    except (TypeError,KeyError,ValueError):pass
            except (OSError,ValueError,TypeError,KeyError):
                pass
    # A fixture may cross midnight UTC. TheSportsDB is additionally queried
    # by UTC date for Baghdad seven-day window, not merely today.
    dates=[begin-dt.timedelta(days=1)+dt.timedelta(days=i) for i in range(WINDOW_DAYS+2)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures=[pool.submit(_sportsdb_date,date) for date in dates]
        for job in concurrent.futures.as_completed(futures):
            try:
                data=job.result()
                for day in (begin+dt.timedelta(days=i) for i in range(WINDOW_DAYS)):
                    results+=parse_sportsdb(data,day.isoformat())
                responded.add("iraq")
            except (OSError,ValueError,TypeError,KeyError):
                pass
    results=within_week(results,begin,end)
    known=official_iraq_snapshot(now)
    # If official verified schedule exists prefer it over missing/unconfirmed
    # Iraqi data; exclude same-date conflicting listings from other providers.
    if known:
        verified_days={local_day(row["kickoff"]) for row in known}
        results=[r for r in results if r["competition_id"]!="iraq"
                 or local_day(r["kickoff"]) not in verified_days]
        results.extend(known)
        responded.add("iraq")
    merged=merge_matches(results)
    message=None
    if len(responded)<len(LEAGUES):
        message="تغطية بعض البطولات غير مكتملة؛ تُعرض المباريات المعلنة فقط."
    return merged,"ok" if len(responded)==len(LEAGUES) else "partial",message,sorted(responded)

def _sportsdb_date(date):
    params=urllib.parse.urlencode({"d":date.isoformat(),"s":"Soccer","l":"Iraqi Stars League"})
    url="https://www.thesportsdb.com/api/v1/json/123/eventsday.php?"+params
    return json.loads(collector.request(url))

def api_week(now,key):
    begin,end=week_window(now)
    # Some API-Football subscriptions require league/season for a date range.
    # Do not suppress ESPN/official fallbacks if the call is rejected.
    url="https://v3.football.api-sports.io/fixtures?"+urllib.parse.urlencode({
        "from":begin.isoformat(),"to":end.isoformat(),"timezone":"Asia/Baghdad"})
    payload=json.loads(collector.request(url,{"x-apisports-key":key}))
    if payload.get("errors"):raise ValueError("API-Football returned errors")
    rows=[]
    for event in payload.get("response",[]):
        league=event.get("league") or {}
        code=collector.league_code(league)
        if not code:continue
        f=event.get("fixture") or {}
        teams=event.get("teams") or {};scores=event.get("goals") or {}
        rows.append(dict(
            id="apifootball-"+str(f.get("id")),competition_id=code,
            league=dict(collector.COMPETITIONS)[code],
            home=(teams.get("home") or {}).get("name") or "—",
            away=(teams.get("away") or {}).get("name") or "—",
            home_goals=scores.get("home"),away_goals=scores.get("away"),
            kickoff=f.get("date"),status=(f.get("status") or {}).get("short") or "NS",
            provider="API-Football"))
    return within_week(rows,begin,end)

def weekly_fixtures(now):
    fallback,status,message,responded=fallback_week(now)
    key=os.environ.get("API_FOOTBALL_KEY","").strip()
    if key:
        try:
            official=api_week(now,key)
            if official:
                authoritative={(row["competition_id"],local_day(row["kickoff"])) for row in official}
                fallback=[f for f in fallback if (f["competition_id"],local_day(f["kickoff"])) not in authoritative]
                fallback=merge_matches(official+fallback)
                responded=sorted(set(responded)|{x["competition_id"] for x in official})
                status="ok" if len(responded)==len(collector.COMPETITIONS) else "partial"
        except (OSError,ValueError,TypeError,KeyError):
            if not message:message="تعذر الاتصال بمصدر المباريات المدفوع؛ استُخدمت المصادر البديلة."
    return fallback,status,message,responded
