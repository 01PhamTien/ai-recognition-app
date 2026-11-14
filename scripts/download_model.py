"""Tải artifact đã cố định phiên bản; kiểm tra SHA256 trước khi thay file."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def download(url: str, path: Path, expected_sha256: str | None = None):
    if path.exists() and expected_sha256 and hashlib.sha256(path.read_bytes()).hexdigest() == expected_sha256:
        return expected_sha256
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    try:
        request = Request(url, headers={"User-Agent": "ai-recognition-app-model-downloader"})
        digest = hashlib.sha256()
        with urlopen(request, timeout=120) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                digest.update(chunk)
                output.write(chunk)
        sha256 = digest.hexdigest()
        if expected_sha256 and sha256 != expected_sha256:
            raise ValueError(f"SHA256 không khớp: {path.name}")
        temporary.replace(path)
        return sha256
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=ROOT / "models")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "models/manifest.json").read_text(encoding="utf-8"))
    for name, artifact in manifest["artifacts"].items():
        digest = download(artifact["url"], args.directory / name, artifact.get("sha256"))
        print(f"{name}: SHA256={digest}")


if __name__ == "__main__":
    main()
