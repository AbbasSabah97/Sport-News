import datetime as dt
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from backend.match_details import (
    parse_details,parse_injuries,parse_h2h,enrich
)
from backend.collector import UTC

class MatchDetailsTest(unittest.TestCase):
    def test_goal_assist_players_and_formation(self):
        item={
            "teams":{"home":{"id":1},"away":{"id":2}},
            "fixture":{"venue":{"name":"ملعب الشعب","city":"بغداد"},"referee":"Ref"},
            "league":{"round":"Round 5"},
            "events":[{"time":{"elapsed":51,"extra":2},"team":{"name":"Home"},
                       "player":{"name":"Scorer"},"assist":{"name":"Assistant"},
                       "type":"Goal","detail":"Normal Goal"}],
            "statistics":[
                {"team":{"id":1},"statistics":[{"type":"Shots on Goal","value":6}]},
                {"team":{"id":2},"statistics":[{"type":"Shots on Goal","value":2}]}],
            "lineups":[{"team":{"name":"Home"},"formation":"4-3-3","coach":{"name":"Coach"},
                "startXI":[{"player":{"id":7,"name":"Forward","number":9,"grid":"4:2","pos":"F"}}],
                "substitutes":[{"player":{"id":5,"name":"Reserve","number":12}}]}],
            "players":[{"team":{"name":"Home"},"players":[{"player":{"name":"Forward","number":9},
                "statistics":[{"games":{"minutes":89,"rating":"7.6","position":"F"},
                               "goals":{"total":1,"assists":0}}]}]}],
        }
        data=parse_details(item)
        self.assertEqual(data["events"][0]["minute"],"51+2")
        self.assertEqual(data["events"][0]["assist"],"Assistant")
        self.assertEqual(data["statistics"]["تسديدات على المرمى"],"6 | 2")
        self.assertEqual(data["lineup_details"][0]["starters"][0]["grid"],"4:2")
        self.assertEqual(data["lineup_details"][0]["substitutes"][0]["name"],"Reserve")
        self.assertEqual(data["player_stats"][0]["rating"],"7.6")
        self.assertEqual(data["venue"],"ملعب الشعب")
    def test_injury_types_are_not_labeled_all_injuries(self):
        arr=[{"fixture":{"id":12},"player":{"name":"P"},
              "team":{"name":"Home"},"type":"Questionable","reason":"Knock"}]
        out=parse_injuries(arr)
        self.assertEqual(out["12"][0]["status"],"Questionable")
        self.assertEqual(out["12"][0]["reason"],"Knock")
    def test_h2h_only_returns_sourced_fixtures(self):
        row={"fixture":{"date":"2026-08-01T20:00:00Z"},
             "teams":{"home":{"name":"A"},"away":{"name":"B"}},
             "goals":{"home":1,"away":0}}
        self.assertEqual(len(parse_h2h([row])),1)
        self.assertEqual(parse_h2h([{}]),[])
    def test_no_key_no_network(self):
        matches=[{"id":"apifootball-15","kickoff":"2026-11-04T18:00:00Z"}]
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{"API_FOOTBALL_KEY":""}):
            result,cache=enrich(matches,dt.datetime(2026,11,4,tzinfo=UTC),
                                tmp+"/cache.json")
        self.assertEqual(result,matches)
        self.assertEqual(cache,{})
    def test_scheduled_near_kickoff_and_cached_absences(self):
        m={"id":"apifootball-15","kickoff":"2026-11-04T18:00:00Z",
           "status":"NS","home_id":1,"away_id":2}
        calls=[]
        def fake_api(endpoint,params,key):
            calls.append(endpoint)
            if endpoint=="fixtures":return [{"fixture":{"id":15}}]
            if endpoint=="injuries":return [
                {"fixture":{"id":15},"player":{"name":"Player"},
                 "type":"Missing Fixture","reason":"Injury"}]
            if endpoint=="fixtures/headtohead":return []
            return []
        with tempfile.TemporaryDirectory() as tmp:
            path=tmp+"/cache.json"
            now=dt.datetime(2026,11,4,16,tzinfo=UTC)
            with patch.dict(os.environ,{"API_FOOTBALL_KEY":"dummy"}),patch(
                "backend.match_details.api_json",side_effect=fake_api):
                result,cache=enrich([dict(m)],now,path)
                self.assertEqual(result[0]["injuries"][0]["player"],"Player")
                with open(path,"w",encoding="utf-8") as f:json.dump(cache,f)
                result2,_=enrich([dict(m)],now+dt.timedelta(minutes=10),path)
            self.assertEqual(calls.count("injuries"),1)
            self.assertIn("injuries",result2[0])
    def test_empty_payload_no_fabricated_detail(self):
        data=parse_details({})
        self.assertEqual(data["events"],[])
        self.assertEqual(data["lineup_details"],[])
        self.assertEqual(data["statistics"],{})
        self.assertEqual(data["player_stats"],[])

if __name__=="__main__":unittest.main()
