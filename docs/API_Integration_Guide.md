# NEXUS ULTRON — API Integration Guide

**Version:** 3.0.0

---

## 1. Web Command Center

Launch the FastAPI server:

```bash
python run_ultron.py --web --host 0.0.0.0 --port 8765
```

All endpoints are relative (`/api/...`). The frontend (`web_ui/static/`) uses the same relative paths.

---

## 2. Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Brand landing page |
| `GET` | `/api/overview` | System status, mode, hardware tier, agents, releases |
| `GET` | `/api/brand-kit` | Brand logo/asset inventory |
| `GET` | `/api/plugins` | List installed skills |
| `POST` | `/api/plugins/execute` | Execute a skill (`skill_id`, `params`) |
| `POST` | `/api/files/calculate` | Safe expression evaluation (`expression`) |
| `POST` | `/api/browser/navigate` | Navigate (payment URLs → `403 Forbidden`) |

---

## 3. Example Requests

### System overview

```bash
curl http://localhost:8765/api/overview
```

Response includes `app_name`, `version`, `hardware.tier`, `connectivity.effective_mode`, `orchestrator.registered_agent_count`, `audit_chain_valid`, and `releases`.

### Safe calculator

```bash
curl -X POST http://localhost:8765/api/files/calculate \
  -H "Content-Type: application/json" \
  -d '{"expression":"sqrt(144) + mean([10,20,30])"}'
```

Response: `{"expression": "...", "result": 32.0}`

### Execute a skill

```bash
curl -X POST http://localhost:8765/api/plugins/execute \
  -H "Content-Type: application/json" \
  -d '{"skill_id":"security_posture_auditor","params":{}}'
```

### Blocked payment (fail closed)

```bash
curl -X POST http://localhost:8765/api/browser/navigate \
  -H "Content-Type: application/json" \
  -d '{"url_or_query":"https://checkout.stripe.com/pay/test"}'
```

Response: `HTTP 403 Forbidden`

---

## 4. Authentication & Security

- The Web Command Center is a local desktop companion; there is no public internet exposure by default (bind to `127.0.0.1` for localhost-only, `0.0.0.0` for LAN).
- Payment/financial navigation is blocked at the API layer (`403`).
- All actions respect the active permission profile and Emergency Stop state.
- Audit log records every API-mediated security decision.

---

## 5. SDK-Style Access (Python)

```python
from fastapi.testclient import TestClient
from nexus_ultron.web_ui.server import create_web_app
from nexus_ultron.runtime import NexusUltronRuntime

rt = NexusUltronRuntime()
app = create_web_app(rt)
client = TestClient(app)

overview = client.get("/api/overview").json()
assert overview["app_name"] == "NEXUS ULTRON"

rt.shutdown()
```

---

## 6. Error Handling

- Blocked payment URLs → `403 Forbidden`.
- Missing/invalid parameters → `400 Bad Request`.
- Internal errors → `500` with the error detail (secrets never included).
