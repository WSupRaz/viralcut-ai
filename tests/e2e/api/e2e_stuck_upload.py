"""Regression: an upload whose complete() lost its response must not strand
the row in upload_pending forever, must not pile up duplicates on retry, and
must not lock the project out via the clip limit.

Reproduces the reported state: several source-video rows for one file, all
status=uploaded / upload_pending=true, object fully assembled in storage.
"""
import argparse, sys, time, uuid
import httpx

ap = argparse.ArgumentParser()
ap.add_argument("--api", default="http://localhost:8000")
args = ap.parse_args()
API = args.api
passed = failed = 0

def check(name, cond, detail=""):
    global passed, failed
    if cond:
        print(f"  PASS  {name}"); passed += 1
    else:
        print(f"  FAIL  {name}" + (f" -- {detail}" if detail else "")); failed += 1

c = httpx.Client(base_url=API, timeout=120)
email = f"stuck-{int(time.time())}-{uuid.uuid4().hex[:6]}@example.com"
c.post("/api/v1/auth/register", json={"email": email, "password": "testpass123", "name": "Stuck"})
tok = c.post("/api/v1/auth/login", json={"email": email, "password": "testpass123"}).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}

pid = c.post("/api/v1/projects", headers=H, json={"title": "stuck upload", "target_aspect_ratio": "9:16"}).json()["id"]

# Build a real small mp4 (>0 bytes, valid ftyp) as a single part.
import subprocess
subprocess.run(["docker","compose","-f","infra/docker-compose.dev.yml","exec","-T","worker","ffmpeg","-v","error","-y",
    "-f","lavfi","-i","testsrc=duration=1:size=320x240:rate=10","-f","lavfi","-i","sine=duration=1",
    "-c:v","libx264","-preset","ultrafast","-pix_fmt","yuv420p","-c:a","aac","/tmp/stuck.mp4"], check=True, capture_output=True)
blob = subprocess.run(["docker","compose","-f","infra/docker-compose.dev.yml","exec","-T","worker","cat","/tmp/stuck.mp4"],
                      check=True, capture_output=True).stdout
size = len(blob)

start = c.post(f"/api/v1/projects/{pid}/source-videos/uploads/start", headers=H,
               json={"filename": "0708.mp4", "content_type": "video/mp4", "size_bytes": size}).json()
sv_id = start["source_video_id"]
url = c.get(f"/api/v1/projects/{pid}/source-videos/{sv_id}/uploads/part-url",
            headers=H, params={"part_number": 1}).json()["upload_url"]
httpx.put(url, content=blob, headers={"Content-Type": "video/mp4"}, timeout=120).raise_for_status()

# First complete succeeds -- this is the call whose RESPONSE we pretend was lost.
r1 = c.post(f"/api/v1/projects/{pid}/source-videos/{sv_id}/uploads/complete", headers=H)
check("first complete succeeds", r1.status_code == 202, f"{r1.status_code} {r1.text[:120]}")

# The client never saw that response, so it retries. Previously: 409 forever.
r2 = c.post(f"/api/v1/projects/{pid}/source-videos/{sv_id}/uploads/complete", headers=H)
check("retrying complete is idempotent, not 409", r2.status_code == 202, f"{r2.status_code} {r2.text[:160]}")

vids = c.get(f"/api/v1/projects/{pid}/source-videos", headers=H).json()
check("row is no longer upload_pending", all(not v["upload_pending"] for v in vids),
      str([(v["id"][:8], v["upload_pending"]) for v in vids]))
check("no duplicate rows created", len(vids) == 1, f"got {len(vids)}")

# Re-uploading the same file must reuse, not create a parallel row.
before = len(c.get(f"/api/v1/projects/{pid}/source-videos", headers=H).json())
s2 = c.post(f"/api/v1/projects/{pid}/source-videos/uploads/start", headers=H,
            json={"filename": "dup.mp4", "content_type": "video/mp4", "size_bytes": size}).json()
again = c.post(f"/api/v1/projects/{pid}/source-videos/uploads/start", headers=H,
               json={"filename": "dup.mp4", "content_type": "video/mp4", "size_bytes": size}).json()
check("re-starting the same file reuses the session", again["source_video_id"] == s2["source_video_id"],
      f'{s2["source_video_id"][:8]} vs {again["source_video_id"][:8]}')
after = len(c.get(f"/api/v1/projects/{pid}/source-videos", headers=H).json())
check("no extra row from the repeated start", after == before + 1, f"{before} -> {after}")

print(f"\n{passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
