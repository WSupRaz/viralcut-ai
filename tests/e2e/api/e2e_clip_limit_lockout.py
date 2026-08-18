"""Reproduce the lockout: a project whose clip quota is entirely consumed by
never-completed upload attempts must still accept a new upload."""
import sys, time, uuid, httpx
API = "http://localhost:8000"
p = f = 0
def check(n, c, d=""):
    global p, f
    print(("  PASS  " if c else "  FAIL  ") + n + (f" -- {d}" if d and not c else "")); 
    globals().__setitem__('p', p + (1 if c else 0)); globals().__setitem__('f', f + (0 if c else 1))

c = httpx.Client(base_url=API, timeout=120)
email = f"lock-{int(time.time())}-{uuid.uuid4().hex[:6]}@example.com"
c.post("/api/v1/auth/register", json={"email": email, "password": "testpass123", "name": "Lock"})
tok = c.post("/api/v1/auth/login", json={"email": email, "password": "testpass123"}).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}
pid = c.post("/api/v1/projects", headers=H, json={"title": "lockout", "target_aspect_ratio": "9:16"}).json()["id"]

limit = c.get("/api/v1/plans/me", headers=H).json()["limits"]["max_clips_per_project"]
print(f"  plan allows {limit} clips/project")

# Start `limit` uploads and never finish any -- exactly the reported state.
for i in range(limit):
    r = c.post(f"/api/v1/projects/{pid}/source-videos/uploads/start", headers=H,
               json={"filename": f"stuck{i}.mp4", "content_type": "video/mp4", "size_bytes": 441975773})
    if r.status_code != 201:
        print("  setup failed:", r.status_code, r.text[:120]); sys.exit(1)

vids = c.get(f"/api/v1/projects/{pid}/source-videos", headers=H).json()
check("setup: quota filled with pending-only rows", len(vids) == limit and all(v["upload_pending"] for v in vids),
      f"{len(vids)} rows")

# The reported failure: this used to 413 "Your plan allows N clip(s)".
r = c.post(f"/api/v1/projects/{pid}/source-videos/uploads/start", headers=H,
           json={"filename": "real.mp4", "content_type": "video/mp4", "size_bytes": 441975773})
check("a new upload is still allowed despite stuck rows", r.status_code == 201,
      f"{r.status_code} {r.text[:140]}")

# And the rows are visible to the client so they can be deleted.
vids = c.get(f"/api/v1/projects/{pid}/source-videos", headers=H).json()
check("stuck rows are returned by the API (so the UI can show + delete them)",
      any(v["upload_pending"] for v in vids))
sv = next(v for v in vids if v["upload_pending"])
d = c.delete(f"/api/v1/projects/{pid}/source-videos/{sv['id']}", headers=H)
check("a stuck row can be deleted", d.status_code == 204, str(d.status_code))

print(f"\n{p} passed, {f} failed")
sys.exit(0 if f == 0 else 1)
