# NovaTech AI Manufacturing Worker Monitoring & Process Compliance System

A local, self-contained prototype for AI-assisted manufacturing-floor monitoring:
worker detection & tracking, zone/workstation awareness, explainable activity
inference (WORKING / IDLE / WALKING), rule-based alerting, and lightweight
process-compliance tracking - built for **NovaTech Manufacturing Pvt. Ltd.**,
**NovaTech Precision Components Plant – Unit 01**.

> **This prototype uses computer vision for operational monitoring. Detection
> and activity inference may be inaccurate and should not be treated as a
> definitive measure of worker performance.**

---

## 1. What is real AI vs. rule-based vs. simulated (read this first)

This project is explicit and transparent about what is genuinely AI-driven,
what is a deterministic rule, and what is simulated for demo purposes. Every
alert, activity label, and process update in the UI carries a `basis` field
(or an on-screen tag) that tells you which of these three categories it
belongs to.

### ✅ Real AI (actual model inference, on-device, CPU or GPU)
- **Person / object detection** — Ultralytics YOLOv8n (`models/yolov8n.pt`),
  a genuine pretrained COCO detector. Verified during development to
  correctly detect and box real people in real photos/video.
- **Pose estimation** — YOLOv8n-Pose (`models/yolov8n-pose.pt`), used as one
  input signal to the Activity Engine (keypoint movement).
- **PPE detection** — architecture and interface (`app/vision/ppe.py`) are
  fully implemented, but **no PPE-classifying model ships with this
  prototype** (COCO weights don't include helmet/vest/glove classes, and
  training a custom model was explicitly out of scope). Until you supply a
  real model at the path in `config.yaml` → `models.ppe`, every PPE field in
  the UI honestly reports **`MODEL_NOT_CONFIGURED`** rather than fabricating
  a result.

### ⚙️ Rule-based / heuristic (deterministic logic, not a trained model)
- **Tracking** — a lightweight custom IOU tracker (`app/vision/tracking.py`),
  one instance per camera, assigns stable "Worker 001/002/…" IDs across
  frames. (Not Ultralytics' built-in ByteTrack/BoT-SORT `persist=True` mode —
  see §6 "Design decisions" for why.)
- **Activity inference (WORKING / IDLE / WALKING / UNKNOWN / OUT_OF_ZONE)** —
  combines bbox-motion speed, pose-keypoint motion, zone membership, and a
  rolling temporal window. Deliberately **not** "person detected = working."
  Every result is labeled `"basis": "rule_based_inference"`, never a raw
  model confidence score.
- **Worker-ID assignment** — tracking IDs are mapped to the 8 demo employee
  records by a simple first-seen/available-slot rule
  (`app/services/worker_service.py`). **This is not facial recognition** and
  is not intended to be — see the Privacy note below.
- **Zone / restricted-area detection**, **idle thresholds**, **PPE-violation
  alerting**, **process-deviation detection**, and the **Rule Engine** itself
  are all deterministic, configurable logic (`config.yaml`, the `rules`
  table).
- **Process-step progression** — because per-step *action recognition* would
  require a custom-trained video model (explicitly out of scope, see §1
  "Not implemented" below), step advancement is a transparent **time-based
  heuristic**: while a worker is `WORKING` inside a zone tied to a process,
  one step is marked complete every `STEP_DWELL_SECONDS` (12s by default).
  This is clearly labeled `"basis": "heuristic_demo_progression"` everywhere
  it appears and is never presented as genuine per-step vision detection.

### 🧪 Simulated (for demo purposes only, always labeled)
- **Synthetic camera fallback** — if a configured camera source (webcam,
  RTSP, mobile URL, file) cannot be opened, the system generates a
  procedurally-drawn video feed (moving rectangle "worker") so the dashboard
  still has 5 live camera tiles. Always overlaid with **"SIMULATED CAMERA"**
  on-screen and reported as `status: "SIMULATED"` via the API.
- **Demo video clips** (`demo/videos/*.mp4`) — procedurally generated, not
  real footage of people (see `demo/generate_demo.py`). Also labeled
  on-screen. Because they are drawn rectangles rather than real human
  shapes, YOLO correctly does **not** detect "person" on them — this is the
  system behaving honestly, not a bug (see §5).
- **Demo Control Panel** (`/settings` page → "Demo Control Panel") — lets you
  manually fire an idle/PPE/restricted-zone/process-deviation/camera-offline
  alert without a real camera. Every alert raised this way has
  `"simulated": true` and is prefixed `[SIMULATED EVENT]`.

### ❌ Not implemented (would require a custom-trained model)
- A manufacturing-specific object detector (screws, tools, boxes,
  finished-product classes) — the base COCO model doesn't have these classes.
  The `DetectionModel` interface (`app/vision/interfaces.py`) is ready to
  accept one.
- A real PPE classifier.
- A real per-step action-recognition model (VideoMAE / SlowFast / X3D /
  MoViNet / RTMPose) for genuine process-step detection.
- Facial recognition (intentionally excluded — see Privacy note, §7).

---

## 2. Technology stack

- **Backend:** FastAPI, Python 3.11+, SQLAlchemy + SQLite, WebSockets
- **Computer vision:** Ultralytics YOLOv8n (detection) + YOLOv8n-Pose, OpenCV,
  a custom lightweight IOU tracker
- **Frontend:** server-rendered Jinja2 + vanilla JS + Chart.js, dark
  "industrial ops center" theme
- **Realtime:** a single `/ws/dashboard` WebSocket broadcasting worker/alert
  updates to every connected browser tab

---

## 3. Installation

```bash
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

> `torch` and `ultralytics` are the two large dependencies (~1-2 GB combined
> including CUDA-capable wheels on some platforms). If you're on a CPU-only
> laptop and want the smaller CPU-only torch build, see the note at the
> bottom of `requirements.txt`.

Generate the demo video clips once (safe to re-run, just overwrites them):

```bash
python demo/generate_demo.py
```

Run the app:

```bash
python run.py
```

Then open **http://localhost:8000**

On first run the app automatically:
1. Creates `data/novatech.db` (SQLite) and all tables
2. Seeds the demo company, 5 cameras, 8 demo workers, 17 zones, 5 processes,
   and 7 rules
3. Starts all 5 camera worker threads (falling back to SIMULATED CAMERA for
   any source it can't open)

### Deploying on Render

This repository includes `render.yaml` for a Render Web Service.

1. Push the project to GitHub. Keep the YOLO model files in `models/`.
2. In Render, choose **New → Blueprint** and select the GitHub repository.
3. Render will read `render.yaml`, install `requirements.txt`, and start the
   FastAPI app on Render's `$PORT`.
4. Open the generated `https://...onrender.com` URL after the first deploy.

Important deployment limits:

- Render cannot access your laptop webcam. Use an accessible IP camera URL or
  keep the bundled demo video sources.
- The free service has an ephemeral filesystem, so the SQLite database and
  generated alert files can be lost after redeploys or restarts. Use a paid
  persistent disk mounted at `/opt/render/project/src/data` for a small demo,
  or move the database to PostgreSQL for a real deployment.
- CPU inference may be slow on free Render instances. A paid instance or a
  separate GPU-capable host is recommended for multiple live cameras.
- Set the `ADMIN_PASSWORD` secret in Render before exposing the app publicly.
  The local-only fallback credentials are `admin` / `novatech123`.

---

## 4. Camera setup

| Camera | Default source | Notes |
|---|---|---|
| CAM-001 Assembly Line A | laptop webcam (`0`) | falls back to SIMULATED CAMERA if no webcam is present |
| CAM-002 Assembly Line B | `demo/videos/cam2_assembly_b.mp4` | |
| CAM-003 Quality Inspection | `demo/videos/cam3_quality.mp4` | |
| CAM-004 Packaging | `demo/videos/cam4_packaging.mp4` | |
| CAM-005 Warehouse | `demo/videos/cam5_warehouse.mp4` | |

**To use your laptop webcam for real detections:** just run the app - CAM-001
defaults to source `0`.

**To use a phone as an IP camera:** install any MJPEG/HTTP IP-camera app on
your phone (many free ones exist for Android/iOS), connect the phone to the
same Wi-Fi network as your laptop, then go to **Settings → Mobile / IP Camera
Test**, enter the stream URL (e.g. `http://192.168.1.100:8080/video`), and
click **Test Camera**. Once confirmed `CONNECTED`, update a camera's source
to that URL via `PUT /api/cameras/{camera_id}` (admin login required) or by
editing `config.yaml`/reseeding.

**To use an uploaded video file:** set a camera's `type` to `video_file` and
`source` to the file path (relative to the project root).

**To add/remove/enable/disable cameras:** admin-authenticated endpoints under
`/api/cameras` (`POST`, `PUT`, `DELETE`). Log in at `/login` first (demo
credentials: `admin` / `novatech123`).

---

## 5. Seeing real AI detections (important!)

The demo video clips and the synthetic-camera fallback are procedurally
drawn shapes, **not real people** — so YOLO correctly reports zero "person"
detections on them. This is intentional (see §1 "Never fake AI"), not a bug.

**To see real detection/tracking/activity inference in action, point CAM-001
at your laptop webcam (default) with a real person in frame.** You should
see a bounding box, a `Worker NNN` label, and a live activity state
(WORKING/IDLE/WALKING) that updates as the person moves or stays still.

---

## 6. Design decisions worth knowing about

- **Per-camera tracking, not a shared tracker.** Ultralytics' built-in
  `model.track(..., persist=True)` keeps its tracker state on the shared
  model/predictor object. Calling it concurrently from 5 camera threads
  would let track IDs and Kalman-filter state leak between unrelated camera
  feeds. Instead, detection (`DetectionEngine.predict_frame`, stateless) is
  shared across cameras for efficiency, while tracking
  (`app/vision/tracking.py`, a small IOU-based tracker) is instantiated
  **once per camera** so tracks can never cross-contaminate.
- **Alert cooldowns.** A persistent condition (e.g. 5 minutes idle) raises
  one alert, not one every frame - see `AlertManager.can_fire()`.
- **State-change-only event logging.** The event log only writes a row when
  a worker's zone or activity state actually *changes*, not every frame.

---

## 7. Privacy

This is an internal manufacturing-monitoring prototype. **No facial
recognition is implemented or intended.** Workers are identified only by
transient computer-vision tracking IDs, which are then mapped to demo
employee records using a simple first-seen/available-slot rule purely so the
dashboard can show readable names. In a real deployment this mapping step
would be replaced by badge/RFID/manual check-in correlation.

---

## 8. Project structure

```
manufacturing-ai-monitor/
├── app/
│   ├── main.py                  # FastAPI app, startup/shutdown, WebSocket
│   ├── api/                     # REST + page routers
│   ├── core/                    # config, database, logging, auth, seed data
│   ├── models/                  # SQLAlchemy models
│   ├── vision/                  # detection, tracking, pose, ppe, zones,
│   │                             activity, camera_stream, camera_manager
│   ├── intelligence/             # process_monitor, rule_engine, alert_manager
│   ├── services/                 # worker_service, event_service, ws_manager
│   ├── templates/                 # Jinja2 pages (dark industrial theme)
│   └── static/                   # css/js
├── models/                       # yolov8n.pt, yolov8n-pose.pt (downloaded)
├── demo/
│   ├── videos/                   # generated demo clips
│   └── generate_demo.py
├── tests/
├── data/                          # SQLite DB + alert snapshots (created at runtime)
├── logs/app.log
├── config.yaml                    # every tunable threshold lives here
├── requirements.txt
├── .env.example
└── run.py
```

---

## 9. API endpoints (selected)

```
GET  /api/cameras                       list cameras + live status
POST /api/cameras                       create camera (admin)
PUT  /api/cameras/{id}                  update camera (admin)
DELETE /api/cameras/{id}                delete camera (admin)
POST /api/cameras/test-connection       test a webcam/RTSP/IP-camera URL
GET  /api/cameras/{id}/stream           MJPEG live annotated stream

GET  /api/workers                       worker roster + live status
GET  /api/workers/{id}                  worker detail + recent events/alerts

GET  /api/alerts                        list alerts (filterable)
POST /api/alerts/{id}/acknowledge       acknowledge an alert

GET  /api/events                        event log (filterable by camera/worker/type/date)

GET  /api/processes                     process definitions
GET  /api/processes/states              live process-instance states
POST /api/processes                     create a process (admin)

GET  /api/zones                         zones (optionally filtered by camera)
POST /api/zones                         create a zone (admin)

GET  /api/dashboard/summary             top-level KPIs for the main dashboard
GET  /api/dashboard/performance          CPU/RAM/GPU/FPS system panel
POST /api/dashboard/login / /logout      admin session

POST /api/demo/simulate/idle|ppe|restricted-zone|process-deviation|camera-offline
POST /api/demo/reset

WS   /ws/dashboard                      realtime worker/alert/camera broadcasts
```

---

## 10. Manual testing checklist

- [ ] `python run.py` starts with no unhandled exceptions
- [ ] `http://localhost:8000` loads the dashboard with 5 camera tiles
- [ ] CAM-001 shows your webcam feed (or "SIMULATED CAMERA" if none present)
- [ ] Standing in front of the webcam produces a `Worker NNN` box that
      updates its activity label as you move/stand still
- [ ] `/workers`, `/alerts`, `/events`, `/analytics`, `/process-monitoring`,
      `/settings` all load without errors
- [ ] Logging in at `/login` with `admin` / `novatech123` succeeds
- [ ] Creating/deleting a camera via `/api/cameras` requires login
- [ ] The Demo Control Panel buttons on `/settings` each produce a new alert
      visible on `/alerts` within a few seconds, tagged `SIMULATED`
- [ ] Unplugging/covering the webcam does not crash the app (falls back
      gracefully)
- [ ] `pytest tests/ -v` passes (23 tests: DB models, zone containment,
      activity state machine, IOU tracker, alert cooldowns, process step
      progression, REST API smoke tests)

---

## 11. Known limitations

- No real PPE model ships with the project (see §1).
- Process-step progression is a time-based heuristic, not real per-step
  vision detection (see §1).
- Worker-to-employee-ID mapping is a simple assignment rule, not biometric
  identification, and will reassign IDs if the camera loses and reacquires
  a person for longer than the track timeout.
- The synthetic-camera fallback and demo video clips are not photorealistic
  and will not produce person detections (intentional, see §5).
- Admin auth is a single hardcoded demo account with a session cookie -
  adequate for a local prototype, not production-grade multi-user auth.
- Tested only on CPU in this environment; a CUDA GPU will be used
  automatically if `torch.cuda.is_available()` and `inference.device: cuda`
  is set in `config.yaml`, but this hasn't been exercised end-to-end here.

## 12. Next recommended improvements

1. Train or source a real PPE-detection model and drop it in at
   `models.ppe` in `config.yaml` — everything downstream (RuleEngine,
   alerts, UI) already knows how to consume it.
2. Replace the time-based process heuristic with a real action-recognition
   model (e.g. a fine-tuned VideoMAE/X3D) once labeled process-step video is
   available.
3. Add badge/RFID-based worker identification to replace the demo
   first-seen assignment rule.
4. Add a canvas-based drag-to-draw zone editor in the UI (the data model
   and API already support arbitrary normalized rectangles - the UI
   currently expects zones to be seeded via `app/core/seed.py` or the
   `/api/zones` POST endpoint).
5. Multi-user auth with per-role permissions instead of one shared admin
   account.
