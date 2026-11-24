"""Extract candidate recipients locally. The result always requires human review."""
import csv
import io
import json
import re
import subprocess
import sys
from contextlib import ExitStack
from pathlib import Path
from threading import BoundedSemaphore
from unicodedata import decimal
from zipfile import ZipFile

import phonenumbers
import pymupdf

from app.core.config import settings
from app.services.meta_whatsapp import WelcomeError, normalize_phone

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 100
MAX_PAGES = 5
_slots = BoundedSemaphore(1)
PHONE_HEADERS = {"phone", "phonenumber", "mobile", "mobilenumber", "whatsapp", "whatsappnumber", "contactnumber", "patientphone"}
NAME_HEADERS = {"name", "patientname", "fullname", "patientfullname", "recipientname"}


def _row(name, phone, source, issue=None):
    original = str(phone if phone is not None else "").strip()
    digits = "".join(str(decimal(char)) if char.isdecimal() else char for char in original)
    try:
        normalized = normalize_phone(digits)
    except WelcomeError:
        normalized = ""
    return {
        "name": str(name if name is not None else "").strip()[:120],
        "original_phone": original[:80],
        "phone": normalized,
        "source": source,
        "issue": issue or (None if normalized else "Check the phone number"),
    }


def _table_rows(rows, source):
    for header_index, header in enumerate(rows, start=1):
        if header_index > 20:
            raise WelcomeError("sheet_headers")
        if any(v is not None and str(v).strip() for v in header):
            break
    else:
        raise WelcomeError("sheet_headers")
    keys = [re.sub(r"[^a-z]", "", str(v).lower()) for v in header]
    phones = [i for i, key in enumerate(keys) if key in PHONE_HEADERS]
    names = [i for i, key in enumerate(keys) if key in NAME_HEADERS]
    if len(phones) != 1 or len(names) > 1:
        raise WelcomeError("sheet_headers")
    for index, cells in enumerate(rows, start=header_index + 1):
        if index > header_index + MAX_ROWS:
            raise WelcomeError("too_many_rows")
        if not any(v is not None and str(v).strip() for v in cells):
            continue
        phone = cells[phones[0]] if len(cells) > phones[0] else None
        name = cells[names[0]] if names and len(cells) > names[0] else None
        # Integral Excel floats represent digits; strings such as scientific notation stay unparsed.
        if isinstance(phone, float) and phone.is_integer() and abs(phone) < 10**15:
            phone = int(phone)
        yield _row(name, phone, f"{source} row {index}")


def _xlsx_rows(data):
    from openpyxl import load_workbook

    with ZipFile(io.BytesIO(data)) as archive:
        members = archive.infolist()
        if len(members) > 256 or sum(item.file_size for item in members) > 20 * 1024 * 1024:
            raise WelcomeError("file_too_large", 413)
    book = load_workbook(io.BytesIO(data), read_only=True, data_only=True, keep_links=False)
    try:
        if len(book.worksheets) != 1:
            raise WelcomeError("one_sheet_required")
        sheet = book.worksheets[0]
        if sheet.max_column and sheet.max_column > 64:
            raise WelcomeError("too_many_columns")
        return list(_table_rows(sheet.iter_rows(max_col=64, values_only=True), "Excel"))
    finally:
        book.close()


def _document_rows(data, kind):
    signature = {"pdf": b"%PDF-", "png": b"\x89PNG\r\n\x1a\n", "jpeg": b"\xff\xd8\xff"}[kind]
    if not data.startswith(signature):
        raise WelcomeError("unsupported_file")
    with ExitStack() as stack:
        document = stack.enter_context(pymupdf.open(stream=data, filetype=kind))
        if document.needs_pass or (kind == "pdf" and not document.is_pdf):
            raise WelcomeError("unsupported_file")
        if kind != "pdf":
            if len(document) != 1 or max(document[0].rect.width, document[0].rect.height) > 6000:
                raise WelcomeError("page_too_large")
            document = stack.enter_context(pymupdf.open(stream=document.convert_to_pdf(), filetype="pdf"))
        if len(document) > MAX_PAGES:
            raise WelcomeError("too_many_pages")
        for page_index, page in enumerate(document, start=1):
            if page.rect.width <= 0 or page.rect.height <= 0 or max(page.rect.width, page.rect.height) > 6000:
                raise WelcomeError("page_too_large")
            text_page = None
            plain = page.get_text(sort=True)
            if kind != "pdf" or not plain.strip() or page.get_images():
                if not settings.WHATSAPP_OCR_TESSDATA:
                    raise WelcomeError("ocr_unavailable", 503)
                dpi = min(200, max(72, int(72 * 3000 / max(page.rect.width, page.rect.height))))
                try:
                    text_page = page.get_textpage_ocr(
                        full=kind != "pdf" or not plain.strip(),
                        dpi=dpi,
                        language=settings.WHATSAPP_OCR_LANGUAGES,
                        tessdata=settings.WHATSAPP_OCR_TESSDATA,
                    )
                except (ValueError, RuntimeError):
                    raise WelcomeError("ocr_unavailable", 503) from None
            # Sorted text reconstructs common name/phone columns into visual lines.
            text = page.get_text(sort=True, textpage=text_page) if text_page else plain
            for line_index, raw in enumerate(text.splitlines(), start=1):
                line = raw.strip()
                if not line:
                    continue
                matches = list(phonenumbers.PhoneNumberMatcher(line, "IN", max_tries=50))
                source = f"Page {page_index}, line {line_index}"
                if len(matches) == 1:
                    match = matches[0]
                    name = (line[:match.start] + " " + line[match.end:]).strip(" \t,:;-|")
                    yield _row(name, match.raw_string, source, "Verify against the original document")
                elif len(matches) > 1:
                    for match in matches:
                        yield _row("", match.raw_string, source, "Multiple numbers on this line")
                elif re.search(r"\d{3}", line) or sum(char.isdecimal() for char in line) >= 7:
                    candidate = max(re.findall(r"[+\d ()-]+", line), key=len, default="").strip()
                    # The suggested candidate is only for editing on manual review.
                    row = _row("", candidate, source, "Check this line for an unclear number")
                    row["phone"] = ""
                    yield row


def _extract(data, kind):
    try:
        if kind == "xlsx":
            rows = iter(_xlsx_rows(data))
        elif kind == "csv":
            rows = _table_rows(csv.reader(io.StringIO(data.decode("utf-8-sig"))), "CSV")
        else:
            rows = _document_rows(data, kind)
        output = []
        try:
            for row in rows:
                if len(output) == MAX_ROWS:
                    raise WelcomeError("too_many_rows")
                output.append(row)
        finally:
            if hasattr(rows, "close"):
                rows.close()
        if not output:
            raise WelcomeError("no_recipients")
        return output
    except WelcomeError:
        raise
    except Exception:
        raise WelcomeError("invalid_file") from None


def extract_recipients(data, kind):
    if not _slots.acquire(blocking=False):
        raise WelcomeError("import_busy", 503)
    try:
        # PyMuPDF and OCR run in a separate process with a hard deadline.
        result = subprocess.run(
            [sys.executable, "-m", "app.services.whatsapp_import", kind],
            cwd=Path(__file__).resolve().parents[2], input=data,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=45, check=True,
        )
        output = json.loads(result.stdout)
        if "error" in output:
            raise WelcomeError(output["error"], output["status"])
        return output["rows"]
    except subprocess.TimeoutExpired:
        raise WelcomeError("import_timeout", 408) from None
    except (OSError, subprocess.CalledProcessError, ValueError, KeyError):
        raise WelcomeError("invalid_file") from None
    finally:
        _slots.release()


if __name__ == "__main__":
    try:
        result = {"rows": _extract(sys.stdin.buffer.read(MAX_BYTES + 1), sys.argv[1])}
    except WelcomeError as error:
        result = {"error": error.code, "status": error.status}
    print(json.dumps(result, ensure_ascii=True))
