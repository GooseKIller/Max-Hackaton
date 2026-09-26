"""Read-only deployment smoke check; does not contact the MAX Bot API."""
import argparse
import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    args = parser.parse_args()
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=20, follow_redirects=True) as client:
        for path in ("/health", "/api/planner/meta", "/openapi.json", "/app/"):
            r = client.get(path)
            r.raise_for_status()
            print(path, r.status_code)
        payload = {"age":18, "balance":3000, "cinema_balance":None, "categories":[], "availability":"both"}
        r = client.post("/api/planner/plans", json=payload)
        r.raise_for_status()
        body = r.json()
        for plan in body["plans"]:
            assert plan["total"] <= 3000 and plan["remaining"] == 3000 - plan["total"]
            assert plan["cinema_total"] == 0
        print("plans:", body["status"], "count:", len(body["plans"]), "synthetic:", body["synthetic"])
        assert client.post("/api/planner/plans", json={**payload, "balance":-1}).status_code == 422
        assert client.post("/webhook", json={}).status_code in (403, 503)
        print("Input validation and closed webhook: OK")


if __name__ == "__main__":
    main()
