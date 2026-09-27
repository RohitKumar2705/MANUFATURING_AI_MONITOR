"""
Generates short synthetic demo video clips for cameras that don't have a
real webcam/mobile feed attached, so the whole 5-camera dashboard can be
demonstrated on a single laptop with only one physical webcam.

These clips are clearly synthetic (procedurally drawn shapes, not footage
of real people) and are always labeled SIMULATED / DEMO on-screen so they
are never mistaken for genuine camera footage or real AI detections.

Run:  python demo/generate_demo.py
"""
import cv2
import numpy as np
import os
import sys

OUT_DIR = os.path.join(os.path.dirname(__file__), "videos")
os.makedirs(OUT_DIR, exist_ok=True)

WIDTH, HEIGHT = 640, 480
FPS = 15
DURATION_SECONDS = 20


def make_clip(filename: str, label: str, n_workers: int, seed: int):
    rng = np.random.default_rng(seed)
    path = os.path.join(OUT_DIR, filename)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(path, fourcc, FPS, (WIDTH, HEIGHT))

    workers = []
    for i in range(n_workers):
        workers.append({
            "cx": rng.uniform(0.2, 0.8) * WIDTH,
            "cy": rng.uniform(0.3, 0.8) * HEIGHT,
            "phase": rng.uniform(0, 6.28),
            "speed": rng.uniform(0.15, 0.6),
            "color": (int(rng.uniform(60, 140)), int(rng.uniform(120, 200)), int(rng.uniform(60, 140))),
        })

    n_frames = FPS * DURATION_SECONDS
    for f in range(n_frames):
        t = f / FPS
        frame = np.full((HEIGHT, WIDTH, 3), (30, 30, 34), dtype=np.uint8)
        for gx in range(0, WIDTH, 40):
            cv2.line(frame, (gx, 0), (gx, HEIGHT), (42, 42, 48), 1)
        for gy in range(0, HEIGHT, 40):
            cv2.line(frame, (0, gy), (WIDTH, gy), (42, 42, 48), 1)

        for w in workers:
            dx = 40 * np.sin(t * w["speed"] + w["phase"])
            dy = 20 * np.cos(t * w["speed"] * 0.7 + w["phase"])
            cx, cy = int(w["cx"] + dx), int(w["cy"] + dy)
            box_w, box_h = 55, 130
            cv2.rectangle(frame, (cx - box_w // 2, cy - box_h // 2),
                          (cx + box_w // 2, cy + box_h // 2), w["color"], -1)
            cv2.circle(frame, (cx, cy - box_h // 2 - 14), 16, w["color"], -1)

        cv2.putText(frame, "SIMULATED CAMERA - DEMO CLIP", (14, 28), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 210, 255), 2, cv2.LINE_AA)
        cv2.putText(frame, label, (14, HEIGHT - 14), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (210, 210, 210), 1, cv2.LINE_AA)
        vw.write(frame)

    vw.release()
    print(f"wrote {path} ({n_frames} frames, {DURATION_SECONDS}s @ {FPS}fps)")


if __name__ == "__main__":
    make_clip("cam2_assembly_b.mp4", "Assembly Line B - demo clip", n_workers=2, seed=2)
    make_clip("cam3_quality.mp4", "Quality Inspection - demo clip", n_workers=1, seed=3)
    make_clip("cam4_packaging.mp4", "Packaging - demo clip", n_workers=2, seed=4)
    make_clip("cam5_warehouse.mp4", "Warehouse / Material Handling - demo clip", n_workers=2, seed=5)
    print("Demo videos generated in", OUT_DIR)
