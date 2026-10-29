import datetime as dt
import unittest
import xml.etree.ElementTree as ET
from backend.collector import UTC, parse_feed, same, cluster, canonical, league_code, SOURCES, COMPETITIONS

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
    def test_competitions(self):
        self.assertEqual(len(COMPETITIONS),7)
        self.assertEqual(league_code({"id":39,"name":"Premier League","country":"England"}),"england")
        self.assertEqual(league_code({"name":"Iraq Stars League","country":"Iraq"}),"iraq")
    def test_exclude_women(self):
        self.assertIsNone(league_code({"id":0,"name":"UEFA Champions League Women","country":"World"}))
if __name__=="__main__":unittest.main()
