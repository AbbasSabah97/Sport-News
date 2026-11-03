"""Publish a compact, seven-competition football feed separately from hourly news.

GitHub Actions can run this every five minutes, but schedules may be delayed.
Never fabricate results. On a provider failure retain only recently verified,
same-week results, with an explicit stale status. No secrets are sent to phones.
"""
import datetime as dt
import json
import os
from pathlib import Path
from .collector import UTC,BAGHDAD,COMPETITIONS
from .weekly_fixtures import weekly_fixtures,week_window

VALID={k for k,_ in COMPETITIONS}
LIVE={"1H","2H","LIVE","HT","ET","BT","P"}
FINAL={"FT","AET","PEN"}
def sanitize_matches(matches):
    result=[]
    ids=set()
    for x in matches:
        if x.get("competition_id") not in VALID:continue
        identifier=str(x.get("id") or "")
        if not identifier or identifier in ids:continue
        ids.add(identifier)
        row={k:x.get(k) for k in (
            "id","competition_id","league","home","away","home_goals",
            "away_goals","kickoff","status","provider","source_url"
        ) if k in x}
        result.append(row)
    return sorted(result,key=lambda x:x.get("kickoff") or "")

def build(now=None,fetcher=None):
    now=now or dt.datetime.now(UTC)
    fetcher=fetcher or weekly_fixtures
    matches,status,message,checked=fetcher(now)
    begin,end=week_window(now)
    matches=sanitize_matches(matches)
    return {
        "schema_version":1,
        "generated_at":now.isoformat(),
        "timezone":"Asia/Baghdad",
        "week_start":begin.isoformat(),"week_end":end.isoformat(),
        "sports_status":status,"sports_error":message,
        "sports_checked":[v for v in checked if v in VALID],
        "matches":matches,
        "live_count":sum(x.get("status") in LIVE for x in matches),
        "competitions":[{"id":k,"name":name} for k,name in COMPETITIONS],
    }

def publish(path=Path("docs/fixtures.json")):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    old={}
    if path.exists():
        try:old=json.loads(path.read_text(encoding="utf-8"))
        except (ValueError,OSError):pass
    now=dt.datetime.now(UTC)
    try:data=build(now)
    except (OSError,ValueError,TypeError,KeyError) as exc:
        data=build(now,fetcher=lambda now:([],"error","تعذر تحديث بيانات المباريات؛ حاول لاحقاً.",[]))
    # Never substitute a previous week's fixtures.
    if not data["matches"] and old.get("week_start")==data["week_start"] and old.get("matches"):
        data["matches"]=sanitize_matches(old["matches"])
        data["sports_status"]="stale"
        data["sports_error"]="تأخر المصدر؛ المعروض آخر جدول محفوظ مع توضيح وقت التحديث."
        data["source_generated_at"]=old.get("generated_at")
    path.write_text(json.dumps(data,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    print("Fixtures:",len(data["matches"]),"status:",data["sports_status"])

if __name__=="__main__":publish()
