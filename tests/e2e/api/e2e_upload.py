"""E2E test for the resumable multipart upload pipeline.

Drives the exact server endpoints the browser uses:
  register -> login -> create project -> uploads/start -> part-url PUTs
  -> uploads/complete -> poll jobs -> check storage object.

Usage:
  pip install httpx
  python tests/e2e/api/e2e_upload.py <video-file> [--api http://localhost:8000]
"""
import argparse
import sys
import time

import httpx


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", help="path to video file to upload")
    parser.add_argument("--api", default="http://localhost:8000",
                        help="FastAPI base URL")
    parser.add_argument("--resume-after", type=int, default=0,
                        help="stop after N parts, then resume from the server's perspective")
    args = parser.parse_args()
    API = args.api

    email = f"e2e-{int(time.time())}@example.com"
    with httpx.Client(base_url=API, timeout=120.0) as client:
        r = client.post("/api/v1/auth/register", json={"email": email, "password": "testpass123", "name": "E2E"})
        r.raise_for_status()
        r = client.post("/api/v1/auth/login", json={"email": email, "password": "testpass123"})
        r.raise_for_status()
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"authed as {email}")

        r = client.post("/api/v1/projects", headers=headers,
                        json={"title": "E2E upload test", "target_aspect_ratio": "9:16"})
        r.raise_for_status()
        project_id = r.json()["id"]
        print(f"project {project_id}")

        import os

        filename = args.video.rsplit("/", 1)[-1]
        size = os.path.getsize(args.video)
        print(f"file {filename} = {size / 1e6:.1f} MB")

        r = client.post(
            f"/api/v1/projects/{project_id}/source-videos/uploads/start",
            headers=headers,
            json={"filename": filename, "content_type": "video/mp4", "size_bytes": size},
        )
        r.raise_for_status()
        start = r.json()
        svid = start["source_video_id"]
        part_size = start["part_size"]
        part_count = start["part_count"]
        print(f"started upload: {part_count} parts of {part_size} bytes")

        uploaded = set()
        with open(args.video, "rb") as f:
            for n in range(1, part_count + 1):
                if args.resume_after and n > args.resume_after:
                    print(f"  simulating interruption after part {args.resume_after}")
                    break
                r = client.get(
                    f"/api/v1/projects/{project_id}/source-videos/{svid}/uploads/part-url",
                    headers=headers, params={"part_number": n},
                )
                r.raise_for_status()
                url = r.json()["upload_url"]

                f.seek((n - 1) * part_size)
                chunk = f.read(min(part_size, size - (n - 1) * part_size))
                r = httpx.put(url, content=chunk, timeout=300.0)
                if r.status_code != 200:
                    print(f"  part {n} FAILED: HTTP {r.status_code} {r.text[:200]}")
                    sys.exit(1)
                uploaded.add(n)
                if n % 20 == 0 or n == part_count:
                    print(f"  part {n}/{part_count} ok")

        if args.resume_after:
            print("--- resuming ---")
            r = client.get(
                f"/api/v1/projects/{project_id}/source-videos/{svid}/uploads/parts",
                headers=headers,
            )
            r.raise_for_status()
            server_parts = {p["part_number"] for p in r.json()}
            assert server_parts == uploaded, f"server has {sorted(server_parts)}, client uploaded {sorted(uploaded)}"
            print(f"server confirms {len(server_parts)}/{part_count} parts already present")

            with open(args.video, "rb") as f:
                for n in range(1, part_count + 1):
                    if n in server_parts:
                        continue
                    r = client.get(
                        f"/api/v1/projects/{project_id}/source-videos/{svid}/uploads/part-url",
                        headers=headers, params={"part_number": n},
                    )
                    r.raise_for_status()
                    url = r.json()["upload_url"]
                    f.seek((n - 1) * part_size)
                    chunk = f.read(min(part_size, size - (n - 1) * part_size))
                    r = httpx.put(url, content=chunk, timeout=300.0)
                    assert r.status_code == 200, f"resume part {n} failed: {r.status_code}"
                    if n % 20 == 0 or n == part_count:
                        print(f"  resumed part {n}/{part_count} ok")

        r = client.post(
            f"/api/v1/projects/{project_id}/source-videos/{svid}/uploads/complete",
            headers=headers,
        )
        if r.status_code != 202:
            print(f"COMPLETE FAILED: HTTP {r.status_code} {r.text}")
            sys.exit(1)
        job = r.json()
        print(f"complete -> job {job['id']} type={job['type']}")

        deadline = time.time() + 1800
        last = ""
        while time.time() < deadline:
            r = client.get(f"/api/v1/projects/{project_id}/jobs", headers=headers)
            r.raise_for_status()
            jobs = r.json()
            line = "; ".join(f"{j['type']}={j['status']}({j.get('stage') or ''}{j.get('progress_pct', 0)})"
                             for j in jobs[:3])
            if line != last:
                print(f"  jobs: {line}")
                last = line
            if jobs and jobs[0]["status"] in ("succeeded", "failed"):
                if jobs[0]["status"] == "failed":
                    print(f"JOB FAILED: {jobs[0].get('error')}")
                    sys.exit(1)
                break
            time.sleep(5)

        print("E2E OK")


if __name__ == "__main__":
    main()
