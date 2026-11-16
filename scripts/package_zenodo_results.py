"""Create the small Zenodo deposit containing observations and derived data."""
from __future__ import annotations

import hashlib
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parent.parent
RELEASE = ROOT / "release"
ARCHIVE = RELEASE / "experimental-observations-v1.0.0.zip"
INCLUDE = (
    ROOT / "README.md",
    ROOT / "PROVENANCE.md",
    ROOT / "LICENSE-DATA.md",
    ROOT / "DATASUS-ATTRIBUTION.md",
    ROOT / "validation",
    ROOT / "phases" / "01-fixed-order" / "config",
    ROOT / "phases" / "01-fixed-order" / "output" / "raw",
    ROOT / "phases" / "01-fixed-order" / "output" / "metadata",
    ROOT / "phases" / "01-fixed-order" / "output" / "derived",
    ROOT / "phases" / "01-fixed-order" / "output" / "tables",
    ROOT / "phases" / "01-fixed-order" / "output" / "figures",
    ROOT / "phases" / "02-order-sensitivity" / "config",
    ROOT / "phases" / "02-order-sensitivity" / "output" / "raw",
    ROOT / "phases" / "02-order-sensitivity" / "output" / "metadata",
    ROOT / "phases" / "02-order-sensitivity" / "output" / "datasets",
    ROOT / "phases" / "02-order-sensitivity" / "output" / "validation",
    ROOT / "phases" / "02-order-sensitivity" / "output" / "derived",
    ROOT / "phases" / "02-order-sensitivity" / "output" / "tables",
    ROOT / "phases" / "02-order-sensitivity" / "output" / "figures",
    ROOT / "phases" / "02-order-sensitivity" / "PROVENANCE_AUDIT.md",
    ROOT / "phases" / "02-order-sensitivity" / "RESULTS_REPORT.md",
)
EXCLUDED_NAMES = {".DS_Store", "fontlist-v3.11.0.json"}


def selected_files() -> list[Path]:
    files: set[Path] = set()
    for item in INCLUDE:
        if item.is_file():
            files.add(item)
        elif item.is_dir():
            files.update(path for path in item.rglob("*") if path.is_file())
        else:
            raise FileNotFoundError(item)
    return sorted(
        (path for path in files if path.name not in EXCLUDED_NAMES and ".matplotlib" not in path.parts),
        key=lambda path: path.relative_to(ROOT).as_posix(),
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_bytes(archive: zipfile.ZipFile, name: str, payload: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=(2026, 9, 26, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, payload)


def main() -> None:
    files = selected_files()
    checksums = []
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        checksums.append(f"{sha256(path)}  {relative}")

    RELEASE.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            write_bytes(archive, path.relative_to(ROOT).as_posix(), path.read_bytes())
        write_bytes(archive, "SHA256SUMS", ("\n".join(checksums) + "\n").encode())

    archive_hash = sha256(ARCHIVE)
    checksum_path = RELEASE / f"{ARCHIVE.name}.sha256"
    checksum_path.write_text(f"{archive_hash}  {ARCHIVE.name}\n")
    print(f"Created {ARCHIVE} with {len(files)} files plus SHA256SUMS")
    print(f"Archive SHA-256: {archive_hash}")


if __name__ == "__main__":
    main()
