import datetime as dt
import unittest
import xml.etree.ElementTree as ET
from backend.collector import UTC, parse_feed, same, cluster, canonical, league_code, classify, SOURCES, COMPETITIONS
from backend.arabic import arabic_text, arabize_items, ARABIC_SOURCES
from backend.football_fallback import parse_espn, parse_sportsdb

NOW = dt.datetime(2026,10,29,12,tzinfo=UTC)
class CollectorTests(unittest.TestCase):
    def test_clean_urls(self):
        self.assertEqual(canonical("https://example.org/story?utm_source=rss&x=1"),"https://example.org/story?x=1")
    def test_parse_rss(self):
        xml=b'<rss><channel><item><title>World news update</title><link>https://example.org/a</link><pubDate>Thu, 29 Oct 2026 11:00:00 GMT</pubDate></item></channel></rss>'
        self.assertEqual(len(parse_feed(xml,SOURCES[0],NOW)),1)
    def test_parse_atom(self):
        atom=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Global news today</title><link href="https://example.org/a"/><updated>2026-10-29T11:00:00Z</updated></entry></feed>'
        self.assertEqual(len(parse_feed(atom,SOURCES[0],NOW)),1)
    def test_merge(self):
        a=dict(id="1",title="Major earthquake strikes coastal region today",url="https://a.org/a",source="A",language="en",published_at=NOW.isoformat())
        b=dict(a,id="2",url="https://b.org/b",source="B",title="Major earthquake strikes coastal region")
        self.assertTrue(same(a,b))
        self.assertEqual(cluster([a,b],NOW)[0]["source_count"],2)
    def test_no_image_fields(self):
        xml=b'<rss><channel><item><title>News example story</title><link>https://example.org/story</link><pubDate>Thu, 29 Oct 2026 11:00:00 GMT</pubDate><enclosure url="https://example.org/picture.jpg" type="image/jpeg"/></item></channel></rss>'
        result=parse_feed(xml,SOURCES[0],NOW)
        self.assertEqual(len(result),1)
        self.assertNotIn("image_url",result[0])
        self.assertNotIn("picture.jpg",str(result[0]))
    def test_article_limit(self):
        arr=[dict(id=str(i),title=f"Unique story headline {i} city {i} topic {i}",url=f"https://example.org/{i}",source="A",language="en",published_at=NOW.isoformat()) for i in range(95)]
        self.assertLessEqual(len(cluster(arr,NOW)),80)
    def test_ai_classification(self):
        self.assertEqual(classify("شركة تطلق نموذجاً جديداً للذكاء الاصطناعي"),"الذكاء الاصطناعي")
        self.assertEqual(classify("تقرير عن تطور الرقائق الإلكترونية"),"العالم")
        self.assertEqual(classify("أخبار الدوري الإنجليزي في مباراة ليفربول"),"رياضة")
    def test_arabic_language_filter(self):
        self.assertTrue(arabic_text("خبر عن الذكاء الاصطناعي والتكنولوجيا"))
        self.assertFalse(arabic_text("OpenAI launches a new research platform"))
        self.assertEqual(arabize_items([{"title":"الذكاء الاصطناعي يغير العالم","summary":"A foreign caption"}],limit=0)[0]["summary"],"")
    def test_ai_feed_is_typed(self):
        self.assertTrue(any(s[3]=="الذكاء الاصطناعي" for s in ARABIC_SOURCES))
        self.assertTrue(all(s[2]=="ar" for s in ARABIC_SOURCES))
    def test_espn_scoreboard_parsing(self):
        event={"events":[{"id":"45","date":"2026-10-29T20:00:00Z",
          "competitions":[{"competitors":[
          {"homeAway":"home","team":{"displayName":"Arsenal"},"score":"2"},
          {"homeAway":"away","team":{"displayName":"Chelsea"},"score":"1"}],
          "status":{"type":{"state":"post","name":"STATUS_FINAL"}}}]}]}
        results=parse_espn(event,"england","2026-10-29")
        self.assertEqual(len(results),1)
        self.assertEqual(results[0]["home_goals"],2)
        self.assertEqual(results[0]["status"],"FT")
    def test_espn_date_baghdad(self):
        event={"events":[{"id":"4","date":"2026-10-29T22:30:00Z",
          "competitions":[{"competitors":[
          {"homeAway":"home","team":{"displayName":"A"}},
          {"homeAway":"away","team":{"displayName":"B"}}]}]}]}
        self.assertEqual(len(parse_espn(event,"england","2026-10-30")),1)
        self.assertEqual(len(parse_espn(event,"england","2026-10-29")),0)
    def test_week_window_is_baghdad_local(self):
        from backend.weekly_fixtures import week_window
        start,end=week_window(dt.datetime(2026,10,29,23,30,tzinfo=UTC))
        self.assertEqual(start.isoformat(),"2026-10-30")
        self.assertEqual(end.isoformat(),"2026-11-05")
    def test_iraq_verifiable_weekly_fixtures(self):
        from backend.weekly_fixtures import official_iraq_snapshot
        now=dt.datetime(2026,10,29,22,30,tzinfo=UTC)
        matches=official_iraq_snapshot(now)
        self.assertGreaterEqual(len(matches),7)
        self.assertTrue(all(x["competition_id"]=="iraq" for x in matches))
        self.assertTrue(all(x.get("source_url","").startswith("https://iraqstarsleague.com/") for x in matches))
        self.assertTrue(all(x["kickoff"].endswith("+00:00") for x in matches))
    def test_official_schedule_expires(self):
        from backend.weekly_fixtures import official_iraq_snapshot
        self.assertEqual(official_iraq_snapshot(dt.datetime(2026,11,1,12,tzinfo=UTC)),[])
    def test_monthly_espn_jobs(self):
        from backend.weekly_fixtures import monthly_tasks,LEAGUES
        jobs=monthly_tasks(dt.date(2026,10,30),dt.date(2026,11,5))
        self.assertEqual(len(jobs),len(LEAGUES)*2)
        self.assertEqual({x[2] for x in jobs},{"202610","202611"})
    def test_weekly_filter_includes_oct_31(self):
        from backend.weekly_fixtures import within_week
        items=[{"kickoff":"2026-10-31T13:30:00+00:00"},{"kickoff":"2026-11-08T13:30:00+00:00"}]
        found=within_week(items,dt.date(2026,10,30),dt.date(2026,11,5))
        self.assertEqual(len(found),1)
    def test_real_standings_parser(self):
        from backend.standings import parse_standings
        data={"children":[{"standings":{"entries":[
            {"team":{"displayName":"Club A"},"stats":[
                {"name":"points","value":21},{"name":"gamesPlayed","value":10},
                {"name":"wins","value":6},{"name":"ties","value":3},
                {"name":"losses","value":1},{"name":"rank","value":1}]}
        ]}}]}
        rows=parse_standings(data,"england")
        self.assertEqual(rows[0]["points"],21)
        self.assertEqual(rows[0]["played"],10)
        self.assertEqual(rows[0]["rank"],1)
    def test_never_invent_standings(self):
        from backend.standings import parse_standings
        self.assertEqual(parse_standings({},"iraq"),[])
        self.assertEqual(parse_standings({"standings":{"entries":[
            {"team":{"name":"Club B"},"stats":[]}]}},"iraq"),[])
    def test_competitions(self):
        self.assertEqual(len(COMPETITIONS),7)
        self.assertEqual(league_code({"id":39,"name":"Premier League","country":"England"}),"england")
        self.assertEqual(league_code({"name":"Iraq Stars League","country":"Iraq"}),"iraq")
    def test_exclude_women(self):
        self.assertIsNone(league_code({"id":0,"name":"UEFA Champions League Women","country":"World"}))
if __name__=="__main__":unittest.main()
