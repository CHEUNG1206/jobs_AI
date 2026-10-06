"""Store an uploaded master CV and read it back as plain text.

Tailored applications copy this text. They do not rewrite it into new
claims. PDF and Word files are reduced to text so the same CV can be
quoted from the tracker page.
"""

from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime, timezone
from email.parser import BytesParser
from email.policy import default
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
UPLOADS = DATA / "uploads"
MASTER_PATH = DATA / "master_cv.json"

ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt", ".md", ".markdown"}
MAX_BYTES = 2_000_000
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def load_master_cv(path: Path = MASTER_PATH) -> dict | None:
    """Return the saved upload, or None when the user has not sent one."""
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not payload.get("text"):
        return None
    return payload


def save_upload(filename: str, raw: bytes, root: Path = DATA) -> dict:
    """Write the original file and a text copy under data/.

    The original is kept so the user can see which file the draft came
    from. Text extraction is what the tailored CV is allowed to quote.
    """
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError("只接受 PDF、DOCX、TXT 或 Markdown。")
    if not raw:
        raise ValueError("檔案是空的。")
    if len(raw) > MAX_BYTES:
        raise ValueError("檔案超過 2MB。")

    text = extract_text(filename, raw)
    if not text.strip():
        raise ValueError("這個檔案裡讀不到文字。請改存成 TXT 或 DOCX。")

    uploads = root / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    safe_name = "master-cv" + suffix
    (uploads / safe_name).write_bytes(raw)
    payload = {
        "filename": Path(filename).name,
        "storedAs": safe_name,
        "uploadedAt": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "characters": len(text),
        "text": text,
        "email": extract_email(text),
    }
    master_path = root / "master_cv.json"
    with master_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return payload


def extract_text(filename: str, raw: bytes) -> str:
    """Pull visible words out of the formats the upload box accepts."""
    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".md", ".markdown"}:
        return raw.decode("utf-8", errors="replace")
    if suffix == ".docx":
        return extract_docx(raw)
    if suffix == ".pdf":
        return extract_pdf(raw)
    raise ValueError("只接受 PDF、DOCX、TXT 或 Markdown。")


def extract_docx(raw: bytes) -> str:
    """Read paragraph text from a Word file without a Word process.

    A docx is a zip archive. The body lives in word/document.xml, and the
    text nodes are enough for quoting the CV back to the user.
    """
    try:
        archive = zipfile.ZipFile(BytesIO(raw))
        xml = archive.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ValueError("這個 DOCX 無法打開。") from exc
    root = ElementTree.fromstring(xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    lines = []
    for node in root.findall(".//w:t", namespace):
        if node.text:
            lines.append(node.text)
    return " ".join(lines)


def extract_pdf(raw: bytes) -> str:
    """Read PDF text when pypdf is installed."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError("伺服器未安裝 PDF 讀取元件。請改上傳 DOCX 或 TXT。") from exc
    reader = PdfReader(BytesIO(raw))
    pages = [(page.extract_text() or "") for page in reader.pages]
    return "\n".join(pages)


def extract_email(text: str) -> str:
    """Return the first address written in the CV, if one is present."""
    match = EMAIL_RE.search(text)
    return match.group(0) if match else ""


def parse_upload(body: bytes, content_type: str) -> tuple[str, bytes]:
    """Take the file part out of a browser multipart form."""
    if "multipart/form-data" not in content_type:
        raise ValueError("上傳格式不正確。")
    header = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
    message = BytesParser(policy=default).parsebytes(header + body)
    if not message.is_multipart():
        raise ValueError("找不到上傳的檔案。")
    for part in message.iter_parts():
        filename = part.get_filename()
        if not filename:
            continue
        data = part.get_payload(decode=True) or b""
        return filename, data
    raise ValueError("找不到上傳的檔案。")


def matching_sentences(cv_text: str, job: dict, limit: int = 8) -> list[str]:
    """Keep uploaded sentences that share a distinctive word with the job.

    This is a highlight, not a rewrite. Sentences that do not overlap are
    left in the full CV and omitted from the short list.
    """
    haystack = " ".join(
        [
            job.get("title", ""),
            job.get("summary", ""),
            " ".join(job.get("requirements") or []),
        ]
    ).lower()
    words = {word for word in re.findall(r"[a-zA-Z][a-zA-Z+#]{4,}", haystack)}
    found = []
    pieces = re.split(r"[\n\r]+|(?<=[.!?])\s+", cv_text)
    for piece in pieces:
        sentence = " ".join(piece.split())
        if len(sentence) < 40:
            continue
        tokens = {word.lower() for word in re.findall(r"[a-zA-Z][a-zA-Z+#]{4,}", sentence)}
        if tokens & words:
            found.append(sentence)
        if len(found) >= limit:
            break
    return found
