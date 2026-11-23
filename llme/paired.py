"""Paired rank intervals and scope-level deployment accounting."""
from collections import defaultdict
from decimal import Decimal
import random

from .run import ARMS


def rank_intervals(rank, routes):
    people = sorted({routes[r["left_item"]]["participant_id"] for r in rank["raw","all"]})
    rng = random.Random(20261123)
    draws = [rng.choices(people,k=len(people)) for _ in range(5000)]
    for group in ("all","ordered","tie"):
        hits = defaultdict(int)
        counts = defaultdict(int)
        for arm in ARMS:
            for r in rank[arm,group]:
                pid = routes[r["left_item"]]["participant_id"]
                hits[pid,arm] += int(r["hit"])
                if arm=="raw":
                    counts[pid] += 1
        for left,right in (("graph","raw"),("graph","flat"),("flat","raw")):
            delta = {p:hits[p,left]-hits[p,right] for p in people}
            n=sum(counts.values())
            samples=[]
            for draw in draws:
                size=sum(counts[p] for p in draw)
                if size:
                    samples.append(100*sum(delta[p] for p in draw)/size)
            samples.sort()
            yield (group,left,right,n,sum(v>0 for v in counts.values()),100*sum(delta.values())/n,
                   samples[int(.025*len(samples))-1],samples[int(.975*len(samples))-1],len(samples))


def metered(event,policy):
    usage=event.get("usage",{})
    prompt=usage.get("promptTokenCount")
    total=usage.get("totalTokenCount")
    if type(total) is not int or type(prompt) is not int or not 0<=prompt<=total:
        return None,None
    if not policy:
        return total,None
    usd=(prompt*Decimal(str(policy["input_usd_per_million"])) +
         (total-prompt)*Decimal(str(policy["output_usd_per_million"])))/1000000
    return total,usd


def amortized(scopes,events):
    policy=events.get("provenance",{}).get("policy")
    for sid,ids in scopes.items():
        for arm in ARMS:
            build=[] if arm=="raw" else [events[sid]]
            calls=[events[f"{arm}/{iid}"] for iid in ids if f"{arm}/{iid}" in events]
            amounts=[metered(event,policy) for event in build+calls]
            complete=len(calls)==len(ids)
            def total(index,values):
                return sum(pair[index] for pair in values) if all(pair[index] is not None for pair in values) else None
            tokens,usd=total(0,amounts),total(1,amounts)
            cold=total(0,amounts[:len(build)+1]) if calls else None
            yield (sid,arm,len(ids),len(calls),complete,cold,tokens,
                   tokens/len(ids) if complete and tokens is not None else None,usd,
                   usd/len(ids) if complete and usd is not None else None)
