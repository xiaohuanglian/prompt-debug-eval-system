import json
import os
import urllib.request

BASE_URL = (os.getenv("GATEWAY_BASE_URL") or os.getenv("STREAMBRIDGE_BASE_URL", "http://127.0.0.1:8080")).rstrip("/")
API_KEY = os.getenv("GATEWAY_API_KEY") or os.getenv("STREAMBRIDGE_API_KEY", "")
USER_ID = os.getenv("GATEWAY_USER_ID") or os.getenv("STREAMBRIDGE_USER_ID", "example-user")
TEMPLATE_ID = os.getenv("GATEWAY_TEMPLATE_ID") or os.getenv("STREAMBRIDGE_TEMPLATE_ID", "YOUR_TEMPLATE_ID")

if not API_KEY:
    raise SystemExit("请设置环境变量 GATEWAY_API_KEY")

payload = {
    "user_id": USER_ID,
    "template_id": TEMPLATE_ID,
    "model": "glm-4.7",
    "params": {
        "target_language": "zh",
        "coach_persona": "Supportive, warm, technically observant coach",
        "training_session": {
            "workout_vector": [{
                "exercise_name": "Squat",
                "target_reps": 10,
                "counters": {
                    "completed_reps": 10,
                    "perfect_reps": 7,
                    "incorrect_reps": 3
                },
                "error_distribution": [
                    {"error": "knee_valgus", "count": 2},
                    {"error": "shallow_depth", "count": 1}
                ]
            }]
        }
    }
}

body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
req = urllib.request.Request(
    url=BASE_URL + "/api/v1/llm/build-and-chat",
    data=body,
    method="POST",
    headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + API_KEY,
    }
)
try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    print(json.dumps(result, ensure_ascii=False, indent=2))
except urllib.error.HTTPError as e:
    err = e.read().decode("utf-8")
    print("HTTP " + str(e.code) + ": " + err)
