"""End-to-end smoke test for the API. Usage: python backend/smoke_test.py [base_url]"""

import sys
import time

import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
USERNAME = f"smoke_{int(time.time())}"


def check(label: str, condition: bool) -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        sys.exit(1)


def main() -> None:
    health = requests.get(f"{BASE}/health", timeout=30).json()
    check("health", health["status"] == "ok")

    register = requests.post(
        f"{BASE}/api/auth/register",
        json={"username": USERNAME, "password": "secret123"},
        timeout=30,
    )
    check("register", register.status_code == 201)
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    login = requests.post(
        f"{BASE}/api/auth/login",
        json={"username": USERNAME, "password": "secret123"},
        timeout=30,
    )
    check("login", login.status_code == 200)
    check("wrong password rejected", requests.post(
        f"{BASE}/api/auth/login",
        json={"username": USERNAME, "password": "nope"},
        timeout=30,
    ).status_code == 401)
    check("unauthenticated history blocked", requests.get(f"{BASE}/api/history", timeout=30).status_code == 401)

    crops = requests.get(f"{BASE}/api/crops", timeout=30).json()
    check("crops", "Wheat" in crops)

    first = requests.post(
        f"{BASE}/api/predict",
        headers=headers,
        json={
            "nitrogen": 80, "phosphorus": 40, "potassium": 40,
            "ph": 6.5, "temperature": 25, "rainfall": 800,
            "crop": "Wheat", "label": "Field A",
        },
        timeout=120,
    )
    check("predict", first.status_code == 200)
    first_body = first.json()
    check("predict has yield", first_body["predicted_yield_kg_ha"] is not None)
    check("predict has top crops", len(first_body["top_crops"]) == 5)
    check("predict has soil analysis", "Nitrogen" in first_body["soil_analysis"])
    check("predict has fertilizer", "combined_summary" in first_body["fertilizer"])

    second = requests.post(
        f"{BASE}/api/predict",
        headers=headers,
        json={
            "nitrogen": 30, "phosphorus": 20, "potassium": 15,
            "ph": 5.4, "temperature": 28, "rainfall": 400,
            "crop": "Wheat", "label": "Field B",
        },
        timeout=120,
    ).json()

    page = requests.get(f"{BASE}/api/history", headers=headers, timeout=30).json()
    check("history lists both runs", page["total"] == 2)

    opened = requests.get(
        f"{BASE}/api/history/{first_body['id']}", headers=headers, timeout=30
    ).json()
    check("open history entry", opened["id"] == first_body["id"])

    compare = requests.get(
        f"{BASE}/api/history/compare",
        headers=headers,
        params={"ids": [first_body["id"], second["id"]]},
        timeout=30,
    )
    check("compare", compare.status_code == 200 and len(compare.json()["entries"]) == 2)
    check("compare flags changes", any(row["changed"] for row in compare.json()["rows"]))
    summary = compare.json()["summary"]
    check("compare summary has one step for two runs", len(summary["steps"]) == 1 and summary["overall"] is None)
    step = summary["steps"][0]
    key_texts = [change["text"] for change in step["key_changes"]]
    check("compare summary orders oldest -> newest", step["from_entry"]["id"] == first_body["id"])
    check("compare summary reports nitrogen change", "Nitrogen decreased by 50 kg/ha." in key_texts)
    check("compare summary reports pH change", "Soil pH decreased from 6.5 to 5.4." in key_texts)
    check("compare summary reports yield change", any(t.startswith("Predicted yield ") for t in key_texts))

    chat = requests.post(
        f"{BASE}/api/chat",
        headers=headers,
        json={"message": "What fertilizer should I use?", "prediction_id": first_body["id"]},
        timeout=90,
    )
    check("chat", chat.status_code == 200 and len(chat.json()["answer"]) > 0)
    print(f"      chat source={chat.json()['source']}: {chat.json()['answer'][:120]}")

    other = requests.post(
        f"{BASE}/api/auth/register",
        json={"username": f"{USERNAME}_other", "password": "secret123"},
        timeout=30,
    ).json()
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}
    check("history is private", requests.get(
        f"{BASE}/api/history/{first_body['id']}", headers=other_headers, timeout=30
    ).status_code == 404)
    check("other user sees empty history", requests.get(
        f"{BASE}/api/history", headers=other_headers, timeout=30
    ).json()["total"] == 0)

    # Crop rotation: advice is computed from the crop actually grown, per user.
    rotation_url = f"{BASE}/api/history/rotation"
    check("rotation: nothing to warn about before any grown crop is recorded", requests.get(
        rotation_url, headers=headers, timeout=30
    ).json()["alerts"] == [])
    for _ in range(3):
        requests.post(
            f"{BASE}/api/predict",
            headers=other_headers,
            json={
                "nitrogen": 60, "phosphorus": 40, "potassium": 40,
                "ph": 6.5, "temperature": 26, "rainfall": 800,
                "crop": "Cotton", "label": "North", "grown_crop": "Cotton",
            },
            timeout=120,
        )
    other_alerts = requests.get(rotation_url, headers=other_headers, timeout=30).json()["alerts"]
    check(
        "rotation: same crop grown 3 times in a row raises an alert",
        len(other_alerts) == 1 and other_alerts[0]["level"] == "alert"
        and other_alerts[0]["crop"] == "Cotton" and other_alerts[0]["field"] == "North",
    )
    check("rotation: alerts are per user (first user still has none)", requests.get(
        rotation_url, headers=headers, timeout=30
    ).json()["alerts"] == [])
    check("rotation: requires login", requests.get(rotation_url, timeout=30).status_code == 401)

    check("delete entry", requests.delete(
        f"{BASE}/api/history/{first_body['id']}", headers=headers, timeout=30
    ).status_code == 200)
    check("clear history", requests.delete(
        f"{BASE}/api/history", headers=headers, timeout=30
    ).json()["deleted"] == 1)
    check("history empty", requests.get(
        f"{BASE}/api/history", headers=headers, timeout=30
    ).json()["total"] == 0)

    print("\nAll smoke checks passed.")


if __name__ == "__main__":
    main()
