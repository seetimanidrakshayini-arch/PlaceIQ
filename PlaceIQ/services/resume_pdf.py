"""PDF validation, storage and text extraction for resumes."""
import os
import uuid
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from config import Config


class ResumeError(Exception):
    pass


def save_pdf(file_storage):
    """Validate an uploaded file is a real PDF within the size limit and store it. Returns (stored_name, size)."""
    if not file_storage or not file_storage.filename:
        raise ResumeError("No file selected.")
    if not file_storage.filename.lower().endswith(".pdf"):
        raise ResumeError("Please upload a PDF file.")
    data = file_storage.read()
    if len(data) > Config.MAX_RESUME_MB * 1024 * 1024:
        raise ResumeError("File is larger than %d MB." % Config.MAX_RESUME_MB)
    if not data.startswith(b"%PDF"):
        raise ResumeError("This file is not a valid PDF.")
    os.makedirs(Config.UPLOAD_DIR, exist_ok=True)
    stored = uuid.uuid4().hex + ".pdf"
    with open(os.path.join(Config.UPLOAD_DIR, stored), "wb") as fh:
        fh.write(data)
    return stored, len(data)


def extract_text(stored_name):
    path = os.path.join(Config.UPLOAD_DIR, stored_name)
    try:
        reader = PdfReader(path)
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                raise ResumeError("The PDF is password protected. Upload an unprotected copy.")
        parts = []
        for page in reader.pages[:6]:
            parts.append(page.extract_text() or "")
        text = "\n".join(parts).strip()
    except (PdfReadError, ValueError, KeyError) as exc:
        raise ResumeError("Could not read this PDF (%s)." % exc.__class__.__name__)
    if len(text) < 40:
        raise ResumeError("No readable text found. The PDF may be a scanned image; upload a text-based PDF.")
    return text


def delete_file(stored_name):
    try:
        os.remove(os.path.join(Config.UPLOAD_DIR, stored_name))
    except OSError:
        pass
