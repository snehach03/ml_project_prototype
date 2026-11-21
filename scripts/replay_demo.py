"""
Replay REAL SWELL-KW minutes of one participant through the live API.

Use it to demo the dashboard without waiting 15+ real minutes. The data is a
research participant's recorded behaviour, NOT yours, and the demo session is
labelled as such in the console.

    # terminal 1 (from project root), allow fast posting:
    MIN_METRIC_INTERVAL_SECONDS=0 uvicorn backend.app.main:app --port 8000
    # terminal 2:
    python scripts/replay_demo.py --participant 7 --sessions 2 --client-id client_demo_replay_0001

Then open the dashboard with that client id in localStorage
(key: behaviorsense_client_id) to see the sessions, or just read the console output.
"""

import argparse
import os
import sys

import requests

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from ml import config, preprocessing  # noqa: E402


def post(base_url, client_id, path, body=None):
    headers = {"X-Client-Id": client_id}
    response = requests.post(base_url + path, json=body, headers=headers, timeout=60)
    response.raise_for_status()
    return response.json()


def replay_block(base_url, client_id, minutes, label):
    started = post(base_url, client_id, "/api/sessions/start",
                   {"consent": True, "consent_version": "2026-11-v1"})
    session_id = started["session_id"]
    print("\n" + label, "| session", session_id, "| baseline from history:", started["baseline_available"])
    last_estimate = None
    for index, minute in enumerate(minutes):
        result = post(base_url, client_id, "/api/sessions/" + session_id + "/metrics", minute)
        last_estimate = result["estimate"]
        if last_estimate["status"] == "ok":
            stress = last_estimate["stress"]
            print("  minute", index + 1, "| score", round(stress["score"], 2), "|", stress["leaning"],
                  "| baseline:", last_estimate["baseline_source"])
        else:
            print("  minute", index + 1, "|", last_estimate["status"])
    post(base_url, client_id, "/api/sessions/" + session_id + "/stop")
    return last_estimate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--participant", default="7")
    parser.add_argument("--sessions", type=int, default=2, help="how many of the participant's blocks to replay")
    parser.add_argument("--client-id", default="client_demo_replay_0001")
    args = parser.parse_args()

    data = preprocessing.load_minute_data()
    person = data[data["participant"] == args.participant].sort_values(["block", "ts"])
    if len(person) == 0:
        raise SystemExit("No data for participant " + args.participant)

    print("REPLAY of SWELL-KW participant", args.participant, "- this is dataset data, not your behaviour.")
    block_ids = sorted(person["block"].unique())[: args.sessions]
    for block_id in block_ids:
        block = person[person["block"] == block_id]
        minutes = []
        for _, row in block.iterrows():
            minute = {}
            for field in config.MINUTE_FIELDS:
                minute[field] = float(row[field])
            minutes.append(minute)
        replay_block(args.base_url, args.client_id, minutes, "Block " + str(block_id) + " (" + str(len(minutes)) + " min)")


if __name__ == "__main__":
    main()
