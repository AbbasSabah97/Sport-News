import datetime as dt
import unittest
from backend.sports_refresh import build,sanitize_matches
from backend.collector import UTC
class SportsRefreshTest(unittest.TestCase):
    def test_only_selected_leagues(self):
        source=[{"id":"a","competition_id":"iraq","kickoff":"2026-11-04T18:00:00+03:00"},
                {"id":"b","competition_id":"bundesliga","kickoff":"2026-11-04T19:00:00+03:00"},
                {"id":"a","competition_id":"iraq","kickoff":"2026-11-04T18:00:00+03:00"}]
        self.assertEqual(len(sanitize_matches(source)),1)
    def test_live_count_and_week(self):
        now=dt.datetime(2026,11,4,11,tzinfo=UTC)
        data,_=build(now,fetcher=lambda _:([{"id":"a","competition_id":"iraq","kickoff":"2026-11-04T20:00:00+03:00","status":"LIVE"}],"ok",None,["iraq"]))
        self.assertEqual(data["live_count"],1)
        self.assertEqual(data["week_start"],"2026-11-04")
        self.assertEqual(data["week_end"],"2026-11-10")
    def test_preserves_live_match_details(self):
        item={"id":"apifootball-15","competition_id":"iraq",
              "kickoff":"2026-11-04T19:00:00+03:00",
              "events":[{"minute":"56","type":"Goal","team":"الزوراء"}],
              "statistics":{"Ball Possession":"55%  |  45%"},
              "lineups":["الزوراء 4-3-3","حارس المرمى"]}
        rows=sanitize_matches([item])
        self.assertEqual(len(rows[0]["events"]),1)
        self.assertEqual(rows[0]["statistics"]["Ball Possession"],"55%  |  45%")
        self.assertEqual(len(rows[0]["lineups"]),2)
    def test_no_fake_score(self):
        rows=sanitize_matches([{"id":"z","competition_id":"worldcup","kickoff":"2026-11-07T17:00:00Z","home_goals":None,"away_goals":None}])
        self.assertIsNone(rows[0]["home_goals"])
        self.assertIsNone(rows[0]["away_goals"])
if __name__=="__main__":unittest.main()
