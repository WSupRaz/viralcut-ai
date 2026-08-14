"""Validation + cancellation tests for the resumable upload endpoints.

Usage:
  pip install httpx
  python tests/e2e/api/e2e_validation.py [--api http://localhost:8000]
"""
import argparse
import time

import httpx

PASS = []
FAIL = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        PASS.append(name)
        print(f"  PASS {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL {name}: {detail}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    args = parser.parse_args()
    API = args.api

    with httpx.Client(base_url=API, timeout=120.0) as client:
        email = f"val-{int(time.time())}@example.com"
        client.post("/api/v1/auth/register", json={"email": email, "password": "testpass123", "name": "Val"}).raise_for_status()
        r = client.post("/api/v1/auth/login", json={"email": email, "password": "testpass123"})
        token = r.json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}
        project_id = client.post("/api/v1/projects", headers=h,
                                 json={"title": "validation", "target_aspect_ratio": "9:16"}).json()["id"]

        # 1. Unsupported content type -> 400
        r = client.post(f"/api/v1/projects/{project_id}/source-videos/uploads/start", headers=h,
                        json={"filename": "x.txt", "content_type": "text/plain", "size_bytes": 100})
        check("unsupported type rejected", r.status_code == 400, r.text)

        # 2. Oversized -> rejected (schema cap at 5 GiB; declare 6 GiB)
        r = client.post(f"/api/v1/projects/{project_id}/source-videos/uploads/start", headers=h,
                        json={"filename": "big.mp4", "content_type": "video/mp4", "size_bytes": 6 * 1024 * 1024 * 1024})
        check("oversized rejected", r.status_code in (413, 422), r.text)

        # 3. Path traversal filename -> sanitized (server-side key safety)
        r = client.post(f"/api/v1/projects/{project_id}/source-videos/uploads/start", headers=h,
                        json={"filename": "../../etc/passwd.mp4", "content_type": "video/mp4", "size_bytes": 100})
        check("start ok for traversal filename", r.status_code == 201, r.text)
        if r.status_code == 201:
            check("key sanitized", "/etc/" not in r.json()["r2_key"] and r.json()["r2_key"].endswith("passwd.mp4"),
                  r.json()["r2_key"])
            svid = r.json()["source_video_id"]
            # cleanup: delete pending
            r2 = client.delete(f"/api/v1/projects/{project_id}/source-videos/{svid}", headers=h)
            check("pending delete ok", r2.status_code == 204, r2.text)

        # 4. Not-a-video content -> complete fails 400 (sizes declared exactly)
        body = b"<html>not a video</html>" + b"0" * 90_000
        r = client.post(f"/api/v1/projects/{project_id}/source-videos/uploads/start", headers=h,
                        json={"filename": "fake.mp4", "content_type": "video/mp4", "size_bytes": len(body)})
        svid = r.json()["source_video_id"]
        for n in range(1, r.json()["part_count"] + 1):
            u = client.get(f"/api/v1/projects/{project_id}/source-videos/{svid}/uploads/part-url",
                           headers=h, params={"part_number": n}).json()["upload_url"]
            start = (n - 1) * r.json()["part_size"]
            httpx.put(u, content=body[start:start + r.json()["part_size"]]).raise_for_status()
        r = client.post(f"/api/v1/projects/{project_id}/source-videos/{svid}/uploads/complete", headers=h)
        check("non-video rejected at complete", r.status_code == 400 and "MP4/MOV" in r.text, r.text)

        # 5. Wrong declared size -> complete fails 400 (declared 99_999 vs uploaded 100_000)
        r = client.post(f"/api/v1/projects/{project_id}/source-videos/uploads/start", headers=h,
                        json={"filename": "size.mp4", "content_type": "video/mp4", "size_bytes": 99_999})
        svid = r.json()["source_video_id"]
        u = client.get(f"/api/v1/projects/{project_id}/source-videos/{svid}/uploads/part-url",
                       headers=h, params={"part_number": 1}).json()["upload_url"]
        httpx.put(u, content=b"\x00\x00\x00\x18ftypmp42" + b"0" * 99_988).raise_for_status()
        r = client.post(f"/api/v1/projects/{project_id}/source-videos/{svid}/uploads/complete", headers=h)
        check("size mismatch rejected", r.status_code == 400 and "corrupted" in r.text, r.text)

        # 6. Cancel = delete pending upload aborts the multipart session
        r = client.post(f"/api/v1/projects/{project_id}/source-videos/uploads/start", headers=h,
                        json={"filename": "cancel.mp4", "content_type": "video/mp4", "size_bytes": 100_000})
        svid = r.json()["source_video_id"]
        u = client.get(f"/api/v1/projects/{project_id}/source-videos/{svid}/uploads/part-url",
                       headers=h, params={"part_number": 1}).json()["upload_url"]
        httpx.put(u, content=b"\x00\x00\x00\x18ftypmp42" + b"0" * 99_988).raise_for_status()
        r = client.delete(f"/api/v1/projects/{project_id}/source-videos/{svid}", headers=h)
        check("cancel deletes pending upload", r.status_code == 204, r.text)
        # parts endpoint must now 404 (session gone)
        r = client.get(f"/api/v1/projects/{project_id}/source-videos/{svid}/uploads/parts", headers=h)
        check("session gone after cancel", r.status_code == 404, r.text)

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
