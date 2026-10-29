"""Arabic-only publishing policy, category feeds and optional translations.

Non-Arabic titles are never released unmodified. A configured official
Google Cloud Translation API key is preferred. An unkeyed public service is
best-effort only and must not be relied upon for operational guarantees.
"""
from __future__ import annotations
import html
import json
import os
import re
import urllib.parse
import urllib.request

CATEGORY_FEEDS = [
    ("أخبار العالم", "العالم", "العالم"),
    ("السياسة الدولية", "سياسة", "سياسة"),
    ("الاقتصاد العالمي", "اقتصاد", "اقتصاد"),
    ("التكنولوجيا والابتكار", "تقنية", "تقنية"),
    ("أخبار كرة القدم", "رياضة", "رياضة"),
    ("أخبار الذكاء الاصطناعي", "الذكاء الاصطناعي", "الذكاء الاصطناعي"),
]
# Explicit topical Google News Arabic-language searches. The provider still
# occasionally returns English results; those are filtered after ingestion.
def topic_feed(query):
    params=urllib.parse.urlencode({
        "q":query+" when:2d","hl":"ar","gl":"IQ","ceid":"IQ:ar"})
    return "https://news.google.com/rss/search?"+params

ARABIC_SOURCES=[
    ("الجزيرة", "https://www.aljazeera.net/rss", "ar",None),
    ("فرانس 24 عربي", "https://www.france24.com/ar/top-stories/rss", "ar",None),
    ("بي بي سي عربي", "https://feeds.bbci.co.uk/arabic/rss.xml", "ar",None),
    ("الأمم المتحدة عربي", "https://news.un.org/feed/subscribe/ar/news/all/rss.xml", "ar",None),
] + [(name,topic_feed(query),"ar",cat) for name,cat,query in CATEGORY_FEEDS]

ARABIC_RE=re.compile(r"[\u0600-\u06ff]")
LATIN_RE=re.compile(r"[A-Za-z]")
def arabic_text(value, min_chars=5):
    ar=len(ARABIC_RE.findall(value or ""))
    latin=len(LATIN_RE.findall(value or ""))
    return ar>=min_chars and ar >= latin

def clean_arabic_summary(value):
    if not value: return ""
    return value if arabic_text(value,4) else ""

def official_google_translate(text):
    key=os.getenv("GOOGLE_TRANSLATE_API_KEY","").strip()
    if not key: return ""
    url="https://translation.googleapis.com/language/translate/v2?"+urllib.parse.urlencode({"key":key})
    payload=json.dumps({"q":text,"target":"ar","format":"text"}).encode()
    request=urllib.request.Request(url,data=payload,headers={"Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(request,timeout=9) as response:
        result=json.loads(response.read(80_000))
    return html.unescape(result["data"]["translations"][0]["translatedText"])

def public_translate(text):
    """Best-effort only; undocumented endpoint may be blocked or changed."""
    params=urllib.parse.urlencode({"client":"dict-chrome-ex","sl":"auto","tl":"ar","q":text})
    url="https://translate.googleapis.com/translate_a/t?"+params
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (WorldPulse; RSS translator)"})
    with urllib.request.urlopen(req,timeout=7) as response:
        data=json.loads(response.read(50_000))
    if isinstance(data,list) and data and isinstance(data[0],list) and data[0]:
        return str(data[0][0])
    return ""

def translate_to_arabic(value):
    if arabic_text(value):return value
    if not value or len(value)<4:return ""
    for provider in (official_google_translate, public_translate):
        if provider is official_google_translate and not os.getenv("GOOGLE_TRANSLATE_API_KEY"):
            continue
        try:
            out=provider(value)
            if arabic_text(out):return out.strip()
        except (OSError,ValueError,IndexError,KeyError,TypeError):
            pass
    return ""

def arabize_items(items, limit=45):
    """Translate only candidates from foreign feeds. Never show English fallback."""
    output=[]
    candidates=0
    for item in items:
        copy=dict(item)
        if arabic_text(copy.get("title","")):
            copy["summary"]=clean_arabic_summary(copy.get("summary",""))
        else:
            if candidates>=limit:continue
            candidates+=1
            translated=translate_to_arabic(copy.get("title",""))
            if not translated:continue
            copy["title"]=translated[:180]
            original_summary=copy.get("summary","")
            # Do not flood free translation providers with long bodies.
            copy["summary"]=clean_arabic_summary(original_summary)
            copy["translated"]=True
        copy["language"]="ar"
        output.append(copy)
    return output
