import unittest
from backend.match_details import parse_details
class MatchDetailTests(unittest.TestCase):
    def test_authorized_event_and_stats_shape(self):
        item={"fixture":{"id":123},"teams":{"home":{"id":1},"away":{"id":2}},
         "events":[{"time":{"elapsed":37},"team":{"name":"Home"},
                    "player":{"name":"A"},"type":"Goal","detail":"Normal Goal"}],
         "statistics":[
           {"team":{"id":1},"statistics":[{"type":"Shots on Goal","value":4}]},
           {"team":{"id":2},"statistics":[{"type":"Shots on Goal","value":2}]}],
         "lineups":[{"team":{"name":"Home"},"formation":"4-3-3",
                     "startXI":[{"player":{"name":"A"}},{"player":{"name":"B"}}]}]}
        data=parse_details(item)
        self.assertEqual(data["events"][0]["minute"],"37")
        self.assertEqual(data["statistics"]["Shots on Goal"],"4  |  2")
        self.assertIn("4-3-3",data["lineups"][0])
        self.assertEqual(data["lineups"][1],"A")
    def test_empty_details_never_fabricated(self):
        self.assertEqual(parse_details({}),{"events":[],"statistics":{},"lineups":[]})
if __name__=="__main__":unittest.main()
