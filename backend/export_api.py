"""Export the public API contract and executable checks; never reads bot secrets."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from app.main import app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", help="Actual public HTTPS origin, once deployed")
    parser.add_argument("--output", default="docs/submission")
    args = parser.parse_args()
    if args.base_url:
        u = urlsplit(args.base_url)
        if u.scheme != "https" or not u.hostname or u.username or u.password or u.query or u.fragment or u.path not in ("", "/"):
            parser.error("base-url must be a public HTTPS origin")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    schema["paths"] = {p: v for p, v in schema["paths"].items() if p.startswith("/api/planner/") or p == "/health"}
    if args.base_url:
        schema["servers"] = [{"url": args.base_url.rstrip("/")}]
    (out / "openapi.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n")
    example = {"age":18, "balance":3000, "cinema_balance":None,
               "categories":[], "availability":"both"}
    checks = {"config_version":"1.0", "solution_id":"pushkin-card-planner",
        "team_id":None, "api_base_url":args.base_url,
        "deployment_status":"address_set_needs_live_check" if args.base_url else "awaiting_hosting",
        "authentication":"none; stateless endpoints do not access bot profiles",
        "checks":[
            {"method":"GET", "path":"/health", "role":"public", "expected_status":200,
             "expected_format":"application/json", "assertions":["status == ok"]},
            {"method":"GET", "path":"/api/planner/meta", "role":"public", "expected_status":200,
             "expected_format":"application/json", "assertions":["city == Казань", "synthetic == true"]},
            {"method":"POST", "path":"/api/planner/plans", "role":"public", "body":example,
             "expected_status":200, "expected_format":"application/json",
             "assertions":["plans[*].total <= balance", "plans[*].remaining >= 0", "synthetic == true"]},
            {"method":"POST", "path":"/api/planner/plans", "role":"public",
             "body":{**example, "balance":-1}, "expected_status":422, "expected_format":"application/json"}
        ]}
    # JSON is valid YAML 1.2; avoids adding a runtime YAML dependency.
    (out / "DATA-API.yaml").write_text(json.dumps(checks, ensure_ascii=False, indent=2) + "\n")
    (out / "example-request.json").write_text(json.dumps(example, ensure_ascii=False, indent=2) + "\n")
    print("API artifacts exported; fill team_id and verify the real HTTPS URL before submission.")


if __name__ == "__main__":
    main()
