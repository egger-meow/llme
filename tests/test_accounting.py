"""A hand-computable scope checks shared construction and missing usage."""
import unittest
from decimal import Decimal

from llme.paired import amortized


class AccountingTest(unittest.TestCase):
    def test_shared_build_and_unmetered_response(self):
        def event(tokens):
            return {"usage":{"promptTokenCount":tokens-1,"totalTokenCount":tokens}}
        events={"s":event(10),"provenance":{"policy":{"input_usd_per_million":1,"output_usd_per_million":3}}}
        for iid in ("a","b"):
            for arm,tokens in (("raw",20),("graph",4),("flat",6)):
                events[f"{arm}/{iid}"]=event(tokens)
        scopes={"s":["a","b"]}
        raw,graph,flat=amortized(scopes,events)
        self.assertEqual(raw[5:8],(20,40,20))
        self.assertEqual(graph[5:8],(14,18,9))
        self.assertEqual(flat[5:8],(16,22,11))
        self.assertEqual(graph[8],Decimal(24)/1000000)
        events["graph/b"]["usage"]={}
        graph=list(amortized(scopes,events))[1]
        self.assertIsNone(graph[6])
        self.assertIsNone(graph[8])
        del events["graph/b"]
        graph=list(amortized(scopes,events))[1]
        self.assertFalse(graph[4])
        self.assertIsNone(graph[7])
