"""Concept walkthrough — HTTP REST API (RFC 0002 Phase E9.4).

Demonstrates the **HTTP / service-style interop layer**: every
Ophamin capability (list scenarios, get a claim, verify a proof,
canonicalize a value, read the proof index, run a scenario)
is reachable over HTTP through a FastAPI app.

The walkthrough uses ``fastapi.testclient.TestClient`` to drive
the app in-process so no real server-process plumbing is needed
to demonstrate the contract. In production the same app runs
under ``ophamin http serve`` (uvicorn) with auto-generated
OpenAPI 3 spec at ``/openapi.json`` and Swagger UI at ``/docs``.

Run with::

    PYTHONPATH=src python examples/walkthrough_http_api.py

Safe to import; demo runs only as ``__main__``. Requires the
``fastapi`` extra (already in the core install).
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from ophamin.http_api import build_app


REPO_ROOT = Path(__file__).resolve().parent.parent
PROOFS_DIR = REPO_ROOT / "proofs" / "measurement_machinery"


def _find_shipped_proof() -> Path:
    candidates = sorted(PROOFS_DIR.rglob("*.json"))
    if not candidates:
        raise SystemExit(
            "No shipped proof found under proofs/measurement_machinery/."
        )
    return candidates[0]


def main() -> None:
    print("# HTTP REST API walkthrough — RFC 0002 Phase E9.4")
    print()
    print("Ophamin's HTTP layer exposes every core capability as a JSON")
    print("REST endpoint. Any consumer that speaks HTTP — a curl script,")
    print("a Kubernetes operator, a service-mesh sidecar, an API gateway")
    print("client — can drive Ophamin without writing Python.")
    print()
    print("This walkthrough exercises 6 of the 8 endpoints in-process via")
    print("FastAPI's TestClient. Each endpoint is one HTTP call; the")
    print("response shape mirrors the shared `ophamin.interfaces._impls`")
    print("contract so behavioural drift between transports is structural.")

    app = build_app()
    client = TestClient(app)

    # === Step 1: liveness probe ===
    print("\n## Step 1: GET /health")
    response = client.get("/health")
    print(f"  {response.request.method} {response.url.path}  →  {response.status_code}")
    print(f"  body: {response.json()}")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    # === Step 2: version ===
    print("\n## Step 2: GET /version")
    response = client.get("/version")
    print(f"  {response.request.method} {response.url.path}  →  {response.status_code}")
    print(f"  body: {response.json()}")
    assert response.status_code == 200
    assert "framework_version" in response.json()

    # === Step 3: list scenarios ===
    print("\n## Step 3: GET /scenarios")
    response = client.get("/scenarios")
    body = response.json()
    print(f"  {response.request.method} {response.url.path}  →  {response.status_code}")
    print(f"  scenarios reported: {len(body['scenarios'])}")
    for s in body["scenarios"][:3]:
        print(f"    - {s['name']:<32} tier={s.get('tier', '?')}")
    print(f"    ... ({len(body['scenarios']) - 3} more)")
    assert response.status_code == 200
    assert len(body["scenarios"]) > 0
    scenario_name = body["scenarios"][0]["name"]

    # === Step 4: get a scenario's pre-registered claim ===
    print(f"\n## Step 4: GET /scenarios/{{name}}/claim  (name={scenario_name})")
    response = client.get(f"/scenarios/{scenario_name}/claim")
    print(f"  {response.request.method} {response.url.path}  →  {response.status_code}")
    body = response.json()
    metadata = body.get("metadata", {})
    print(f"  scenario:    {body.get('name', '?')}")
    print(f"  tier:        {metadata.get('tier', '?')}")
    print(f"  target:      {metadata.get('target', '?')}")
    statement = metadata.get("goal", "?")
    print(f"  goal:        {statement[:80]}{'...' if len(statement) > 80 else ''}")
    assert response.status_code == 200

    # === Step 5: canonicalize a JSON value ===
    print("\n## Step 5: POST /canonicalize")
    value = {"a": 1, "b": 2.5, "c": [3, 4]}
    value_json = json.dumps(value)
    response = client.post("/canonicalize", json={"value_json": value_json})
    body = response.json()
    print(f"  {response.request.method} {response.url.path}  →  {response.status_code}")
    print(f"  input:           {value_json}")
    print(f"  canonical:       {body['canonical']}")
    print(f"  sha256_hex:      {body['sha256_hex'][:32]}...")
    print(f"  hmac_sha256_hex: {body['hmac_sha256_hex'][:32]}...")
    assert response.status_code == 200
    assert body["canonical"].startswith("{")

    # === Step 6: verify a shipped proof ===
    proof_path = _find_shipped_proof()
    print(f"\n## Step 6: POST /verify  (proof: {proof_path.name})")
    proof_json = proof_path.read_text()
    response = client.post("/verify", json={"proof_json": proof_json})
    body = response.json()
    print(f"  {response.request.method} {response.url.path}  →  {response.status_code}")
    print(f"  verified:        {body['verified']}")
    print(f"  verdict.outcome: {body['verdict']['outcome']}")
    print(f"  proof_id:        {body['proof_id'][:32]}...")
    assert response.status_code == 200
    assert body["verified"] is True

    # === Step 7: read the proof index ===
    print(f"\n## Step 7: POST /proofs/index")
    response = client.post(
        "/proofs/index", json={"directory": str(PROOFS_DIR)}
    )
    body = response.json()
    print(f"  {response.request.method} {response.url.path}  →  {response.status_code}")
    print(f"  directory:           {body.get('directory', '?')}")
    print(f"  total_proofs:        {body.get('total_proofs', 0)}")
    counts = body.get("counts_by_scenario", {})
    if counts:
        print(f"  counts by scenario (first 3):")
        for name, count in list(counts.items())[:3]:
            print(f"    - {name}: {count}")
    assert response.status_code == 200

    # === Step 8: OpenAPI surface ===
    print(f"\n## Step 8: GET /openapi.json (auto-generated by FastAPI)")
    response = client.get("/openapi.json")
    body = response.json()
    print(f"  {response.request.method} {response.url.path}  →  {response.status_code}")
    print(f"  openapi version: {body.get('openapi', '?')}")
    print(f"  api title:       {body.get('info', {}).get('title', '?')}")
    print(f"  api version:     {body.get('info', {}).get('version', '?')}")
    print(f"  paths exposed:   {len(body.get('paths', {}))}")
    for path in sorted(body.get("paths", {}).keys()):
        print(f"    - {path}")
    assert response.status_code == 200
    assert body["openapi"].startswith("3.")

    # === Invariants — what we MUST pin ===
    assert len(body["paths"]) >= 8, "Should expose at least 8 endpoints"
    assert "/verify" in body["paths"]
    assert "/canonicalize" in body["paths"]

    print("\n✓ HTTP REST API walkthrough complete. Contract validated.")


if __name__ == "__main__":
    main()
