"""Conservative generation budget. One micro-USD per token equals $1 per million."""
import json
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR


def read_policy(path, model):
    with path.open(encoding="utf8") as stream:
        policy=json.load(stream)
    return validate_policy(policy, model)


def validate_policy(policy, model):
    if model != policy.get("model") or not policy.get("price_source_date"):
        raise ValueError("Policy needs matching model and dated price source")
    for key in ("budget_usd","input_usd_per_million","output_usd_per_million"):
        value=Decimal(str(policy[key]))
        if not value.is_finite() or value <= 0:
            raise ValueError(f"Expected positive finite {key}")
    for key in ("input_limit","output_limit"):
        if type(policy[key]) is not int or policy[key]<=0:
            raise ValueError(f"Invalid {key}")
    return policy


def reservation(policy, inputs, outputs):
    if type(inputs) is not int or inputs<0 or inputs>policy["input_limit"] or outputs>policy["output_limit"]:
        raise ValueError("Request exceeds frozen model capacity")
    cost=inputs*Decimal(str(policy["input_usd_per_million"])) + outputs*Decimal(str(policy["output_usd_per_million"]))
    return int(cost.to_integral_value(rounding=ROUND_CEILING))


def authorize(db, policy, amount):
    limit=(Decimal(str(policy["budget_usd"]))*1000000).to_integral_value(rounding=ROUND_FLOOR)
    used=db.execute("SELECT COALESCE(sum(reserved_micro_usd),0) FROM attempts").fetchone()[0]
    if used+amount>limit:
        raise SystemExit("Run-wide generation budget reached before sending request.")
