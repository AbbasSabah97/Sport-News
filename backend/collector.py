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
        results.append(dict(id=hashlib.sha256(url.encode()).hexdigest()[:18],title=title[:180],
            summary=clean(field(item,"description","summary","content"))[:150],
            url=url,source=(field(item,"source") if source[0].startswith("أخبار ") and field(item,"source") else source[0]),language=source[2],published_at=published.isoformat(),
            category=(source[3] if len(source)>3 else None)))
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
    def words(*phrases):
        return any(re.search(r"(?<!\w)"+re.escape(norm(phrase))+r"(?!\w)",n) for phrase in phrases)
    if (words("الذكاء الاصطناعي","الذكاء التوليدي","chatgpt","openai","gemini ai","artificial intelligence","machine learning","نماذج اللغة","تعلم الالة","تعلم الآلة","روبوتات المحادثة")
            or "للذكاء الاصطناعي" in n or "ذكاء اصطناعي" in n):
        return "الذكاء الاصطناعي"
    if words("رياضة","دوري","مباراة","مباريات","كرة القدم","football","soccer","league","champions league","كأس","كاس"):
        return "رياضة"
    if words("اقتصاد","اقتصادية","الأسهم","بورصة","تضخم","النفط","اقتصادي","البنوك","الأسواق","economy","inflation","stock market","oil prices","business"):
        return "اقتصاد"
    if words("تقنية","تكنولوجيا","التقنية","تكنولوجي","هواتف","برمجيات","cybersecurity","technology","software","chips"):
        return "تقنية"
    if words("انتخابات","الرئيس","البرلمان","الحكومة","الرئاسية","دبلوماسية","president","minister","election","government","diplomacy"):
        return "سياسة"
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
        a["related_sources"]=sorted(g["sources"])[:5]
        a["category"]=a.get("category") or classify(a["title"])
        age=max(0,(now-dt.datetime.fromisoformat(a["published_at"])).total_seconds()/3600)
        a["rank"]=round(2.5*min(len(g["sources"]),4)+max(0,3-age/6),2)
        results.append(a)
    return sorted(results,key=lambda a:(a["rank"],a["published_at"]),reverse=True)[:80]

def news(now):
    from .arabic import ARABIC_SOURCES,arabize_items,arabic_text
    sources=ARABIC_SOURCES+SOURCES
    raw=[];warnings=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=9) as pool:
        jobs={pool.submit(request,source[1]):source for source in sources}
        for job in concurrent.futures.as_completed(jobs):
            source=jobs[job]
            try:
                incoming=parse_feed(job.result(),source,now)
                for a in incoming:
                    a["category"]=a.get("category") or classify(a["title"])
                raw.extend(incoming)
            except (OSError,ValueError,ET.ParseError,TimeoutError) as exc:
                warnings.append(f"{source[0]}: {type(exc).__name__}")
    # Arabic originals are always prioritized. Best-effort automatic translation
    # extends coverage, but untranslated English headlines are never published.
    raw.sort(key=lambda x:(0 if arabic_text(x["title"]) else 1,-dt.datetime.fromisoformat(x["published_at"]).timestamp()))
    translated=arabize_items(raw,limit=30)
    clean_items=[]
    for a in translated:
        if not arabic_text(a["title"]):continue
        if a.get("summary") and not arabic_text(a["summary"],4): a["summary"]=""
        a.pop("translated",None)
        clean_items.append(a)
    unique=cluster(clean_items,now)
    # Balance all real categories rather than letting a single source dominate
    # the first 80 stories. We never invent placeholder news for empty sections.
    topics=["العالم","سياسة","اقتصاد","تقنية","الذكاء الاصطناعي","رياضة"]
    balanced=[];seen=set()
    for topic in topics:
        candidates=[a for a in unique if a["category"]==topic]
        for a in candidates[:12]:
            if a["id"] not in seen:
                balanced.append(a);seen.add(a["id"])
    for a in unique:
        if a["id"] not in seen and len(balanced)<80:
            balanced.append(a);seen.add(a["id"])
    balanced=balanced[:80]
    counts={name:sum(a["category"]==name for a in balanced) for name in topics}
    digest=[{k:v for k,v in a.items() if k in ("id","source","source_count","url","category")} | {"headline":a["title"]} for a in balanced[:10]]
    return balanced,digest,warnings,counts

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
    from .weekly_fixtures import weekly_fixtures
    return weekly_fixtures(now)

def build(now=None):
    now=now or dt.datetime.now(UTC)
    stories,digest,warnings,counts=news(now)
    matches,status,sports_error,checked=fixtures(now)
    from .standings import get_standings
    tables=get_standings()
    return dict(schema_version=1,generated_at=now.isoformat(),timezone="Asia/Baghdad",
        local_date=now.astimezone(BAGHDAD).date().isoformat(),news_status="ok" if stories else "unavailable",
        news=stories,digest=digest,digest_note="عناوين عربية موجزة؛ افتح رابط المصدر للاطلاع على التفاصيل.",
        category_counts=counts,
        source_warnings=warnings,sports_status=status,sports_error=sports_error,
        competitions=[dict(id=k,name=v) for k,v in COMPETITIONS],matches=matches,
        sports_checked=checked,standings=tables,week_start=now.astimezone(BAGHDAD).date().isoformat(),
        week_end=(now.astimezone(BAGHDAD).date()+dt.timedelta(days=6)).isoformat())

def main():
    path=Path(os.getenv("OUTPUT_JSON","docs/feed.json"))
    path.parent.mkdir(parents=True,exist_ok=True)
    result=build()
    if path.exists():
        try:old=json.loads(path.read_text(encoding="utf-8"))
        except (ValueError,OSError):old={}
        if not result["news"] and old.get("news"):
            from .arabic import arabic_text
            result["news"]=[{k:v for k,v in item.items() if k!="image_url"}
                            for item in old["news"][:80] if arabic_text(item.get("title",""))]
            result["digest"]=[d for d in old.get("digest",[])[:10] if arabic_text(d.get("headline",""))]
            result["news_status"]="stale"
        if result["sports_status"]=="error" and old.get("local_date")==result["local_date"] and old.get("matches"):
            result["matches"]=old["matches"];result["sports_status"]="stale"
    path.write_text(json.dumps(result,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    print(f"Updated {path}: {len(result['news'])} news / {len(result['matches'])} fixtures")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
