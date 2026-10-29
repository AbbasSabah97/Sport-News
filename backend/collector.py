"""Hourly news and football aggregation; standard library only."""
from __future__ import annotations

import concurrent.futures
import datetime as dt
import difflib
import email.utils
import hashlib
import html
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc
BAGHDAD = ZoneInfo("Asia/Baghdad")
SOURCES = [
 ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml", "en"),
 ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml", "en"),
 ("BBC Technology", "https://feeds.bbci.co.uk/news/technology/rss.xml", "en"),
 ("Al Jazeera English", "https://www.aljazeera.com/xml/rss/all.xml", "en"),
 ("الجزيرة", "https://www.aljazeera.net/rss", "ar"),
 ("DW", "https://rss.dw.com/rdf/rss-en-all", "en"),
 ("The Guardian", "https://www.theguardian.com/world/rss", "en"),
 ("France 24 عربي", "https://www.france24.com/ar/top-stories/rss", "ar"),
 ("Euronews", "https://www.euronews.com/rss", "en"),
 ("UN News", "https://news.un.org/feed/subscribe/en/news/all/rss.xml", "en"),
 ("NPR", "https://feeds.npr.org/1001/rss.xml", "en"),
 ("Sky News", "https://feeds.skynews.com/feeds/rss/world.xml", "en"),
 ("NYT World", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "en"),
 ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index", "en"),
 ("ProPublica", "https://www.propublica.org/feeds/propublica/main", "en"),
]
COMPETITIONS = [
 ("iraq","الدوري العراقي"),("spain","الدوري الإسباني"),("england","الدوري الإنجليزي"),
 ("ucl","دوري أبطال أوروبا"),("worldcup","كأس العالم"),
 ("asiacup","كأس أمم آسيا"),("euro","كأس أمم أوروبا")]
IGNORE = set("the and for with from that this after into over under في من على الى إلى ان أن عن مع حتى بعد قبل".split())

def request(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent":"WorldPulse/0.3 (+source attribution)","Accept":"application/rss+xml, application/atom+xml, application/json, */*", **(headers or {})})
    with urllib.request.urlopen(req, timeout=14) as response:
        data=response.read(2_000_001)
        if len(data)>2_000_000: raise ValueError("source too large")
        return data

def clean(value):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", html.unescape(value or ""))).strip()

def norm(s):
    s=s.casefold()
    s=re.sub(r"[\u064b-\u065f\u0670\u0640]","",s).translate(str.maketrans("أإآىة","ااايه"))
    return re.sub(r"[^\w\u0600-\u06ff]+", " ",s).strip()

def tokens(s):
    return {x for x in norm(s).split() if len(x)>2 and x not in IGNORE}

def canonical(url):
    p=urllib.parse.urlsplit(url.strip())
    if p.scheme not in ("http","https") or not p.hostname or p.username: return ""
    qs=[(k,v) for k,v in urllib.parse.parse_qsl(p.query) if not k.lower().startswith("utm_") and k.lower() not in ("fbclid","gclid")]
    return urllib.parse.urlunsplit((p.scheme,p.netloc.lower(),p.path.rstrip("/") or "/",urllib.parse.urlencode(qs),""))

def date(value, now):
    try:
        v=email.utils.parsedate_to_datetime(value)
    except (TypeError,ValueError,IndexError):
        try: v=dt.datetime.fromisoformat(value.replace("Z","+00:00"))
        except (AttributeError,ValueError): return now
    return v.replace(tzinfo=UTC) if v.tzinfo is None else v.astimezone(UTC)

def field(element,*tags):
    for child in element:
        if child.tag.split("}")[-1].lower() in tags and child.text:
            return child.text.strip()
    return ""

def image(element):
    for child in element:
        tag=child.tag.split("}")[-1].lower()
        if tag not in ("thumbnail","enclosure","content"): continue
        if tag=="enclosure" and not child.get("type","").startswith("image/"): continue
        url=child.get("url","")
        p=urllib.parse.urlsplit(url)
        if p.scheme=="https" and p.hostname and not p.username: return url
    return None

def parse_feed(xml, source, now):
    root=ET.fromstring(xml)
    results=[]
    for item in root.iter():
        if item.tag.split("}")[-1].lower() not in ("item","entry"):continue
        title=clean(field(item,"title"))
        url=field(item,"link")
        if not url:
            for child in item:
                if child.tag.split("}")[-1].lower()=="link" and child.get("rel","alternate")=="alternate":
                    url=child.get("href","")
                    if url:break
        url=canonical(url)
        published=date(field(item,"pubdate","published","updated","date"),now)
        if not title or not url or not (-900<=(now-published).total_seconds()<=172800): continue
        results.append(dict(id=hashlib.sha256(url.encode()).hexdigest()[:18],title=title[:240],
            summary=clean(field(item,"description","summary","content"))[:220],
            url=url,source=source[0],language=source[2],published_at=published.isoformat(),image_url=image(item)))
    return results

def same(a,b):
    if a["url"]==b["url"]: return True
    ta,tb=tokens(a["title"]),tokens(b["title"])
    if len(ta & tb)<3:return False
    overlap=len(ta&tb)/max(1,min(len(ta),len(tb)))
    similarity=difflib.SequenceMatcher(None,norm(a["title"]),norm(b["title"])).ratio()
    return overlap>=0.76 or (overlap>=0.58 and similarity>=0.68)

def classify(title):
    n=norm(title)
    for name,words in [
        ("اقتصاد",("economy","market","inflation","bank","stock","oil","اقتصاد","نفط","مال")),
        ("تقنية",("technology","artificial intelligence","software","cyber","chip","ذكاء","تقنيه","تقنية")),
        ("رياضة",("football","league","soccer","goal","دوري","كاس","مباراه")),
        ("سياسة",("election","president","minister","parliament","انتخابات","رئيس","وزير"))]:
        if any(w in n for w in words):return name
    return "العالم"

def cluster(items,now):
    groups=[]
    for item in sorted(items,key=lambda x:x["published_at"],reverse=True):
        hit=next((g for g in groups if same(g["lead"],item)),None)
        if hit:hit["sources"].add(item["source"])
        else: groups.append({"lead":item,"sources":{item["source"]}})
    results=[]
    for g in groups:
        a=dict(g["lead"])
        a["source_count"]=len(g["sources"])
        a["related_sources"]=sorted(g["sources"])
        a["category"]=classify(a["title"])
        age=max(0,(now-dt.datetime.fromisoformat(a["published_at"])).total_seconds()/3600)
        a["rank"]=round(2.5*min(len(g["sources"]),4)+max(0,3-age/6),2)
        results.append(a)
    return sorted(results,key=lambda a:(a["rank"],a["published_at"]),reverse=True)[:120]

def news(now):
    raw=[];warnings=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=7) as pool:
        jobs={pool.submit(request,s[1]):s for s in SOURCES}
        for job in concurrent.futures.as_completed(jobs):
            source=jobs[job]
            try:raw.extend(parse_feed(job.result(),source,now))
            except (OSError,ValueError,ET.ParseError,TimeoutError) as exc:
                warnings.append(f"{source[0]}: {type(exc).__name__}")
    unique=cluster(raw,now)
    digest=[{k:v for k,v in a.items() if k in ("id","source","source_count","url","category")} | {"headline":a["title"]} for a in unique[:10]]
    return unique,digest,warnings

def league_code(league):
    lid=league.get("id"); name=norm(league.get("name",""));country=norm(league.get("country",""))
    if any(x in name for x in ("women","u17","u19","u20","u21","qualification","qualifiers")):return None
    if country=="iraq" and any(x in name for x in ("iraq stars league","iraqi stars league","iraqi premier league","iraq premier league","iraqi league","stars league")):return "iraq"
    if lid==39 or (country=="england" and name=="premier league"):return "england"
    if lid==140 or (country=="spain" and name in ("la liga","primera division")):return "spain"
    if lid==2 or name=="uefa champions league":return "ucl"
    if lid==1 or name in ("world cup","fifa world cup"):return "worldcup"
    if name in ("afc asian cup","asian cup","afc asian cup finals"):return "asiacup"
    if name in ("uefa euro","euro championship","european championship","uefa european championship"):return "euro"
    return None

def fixtures(now):
    key=os.environ.get("API_FOOTBALL_KEY","").strip()
    if not key:return [],"not_configured","أضف API_FOOTBALL_KEY في GitHub Secrets"
    day=now.astimezone(BAGHDAD).date().isoformat()
    url="https://v3.football.api-sports.io/fixtures?"+urllib.parse.urlencode({"date":day,"timezone":"Asia/Baghdad"})
    try:
        payload=json.loads(request(url,{"x-apisports-key":key}))
        if payload.get("errors"):return [],"error",str(payload["errors"])[:250]
        rows=[]
        for item in payload.get("response",[]):
            lg=item.get("league") or {};code=league_code(lg)
            if not code:continue
            fx=item.get("fixture") or {};teams=item.get("teams") or {};goals=item.get("goals") or {}
            rows.append(dict(id=str(fx.get("id","")),competition_id=code,league=dict(COMPETITIONS)[code],
                home=(teams.get("home") or {}).get("name") or "—",away=(teams.get("away") or {}).get("name") or "—",
                home_goals=goals.get("home"),away_goals=goals.get("away"),
                kickoff=fx.get("date",""),status=(fx.get("status") or {}).get("short") or "TBD"))
        return sorted(rows,key=lambda x:(x["kickoff"],x["league"])),"ok",None
    except (OSError,ValueError,TimeoutError) as exc:
        return [],"error",f"تعذر تحديث المباريات: {type(exc).__name__}"

def build(now=None):
    now=now or dt.datetime.now(UTC)
    stories,digest,warnings=news(now)
    matches,status,sports_error=fixtures(now)
    return dict(schema_version=1,generated_at=now.isoformat(),timezone="Asia/Baghdad",
        local_date=now.astimezone(BAGHDAD).date().isoformat(),news_status="ok" if stories else "unavailable",
        news=stories,digest=digest,digest_note="ملخص آلي للعناوين؛ افتح الخبر لمعرفة التفاصيل.",
        source_warnings=warnings,sports_status=status,sports_error=sports_error,
        competitions=[dict(id=k,name=v) for k,v in COMPETITIONS],matches=matches)

def main():
    path=Path(os.getenv("OUTPUT_JSON","docs/feed.json"))
    path.parent.mkdir(parents=True,exist_ok=True)
    result=build()
    if path.exists():
        try:old=json.loads(path.read_text(encoding="utf-8"))
        except (ValueError,OSError):old={}
        if not result["news"] and old.get("news"):
            result["news"]=old["news"];result["digest"]=old.get("digest",[]);result["news_status"]="stale"
        if result["sports_status"]=="error" and old.get("local_date")==result["local_date"] and old.get("matches"):
            result["matches"]=old["matches"];result["sports_status"]="stale"
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Updated {path}: {len(result['news'])} news / {len(result['matches'])} fixtures")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
