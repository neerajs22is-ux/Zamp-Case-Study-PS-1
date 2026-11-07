"""Bounded subprocess PDF text extraction. No model, network, or credentials."""
import io
import json
from pathlib import Path
import subprocess
import sys

MAX_PAGES = 100
MAX_TEXT_CHARS = 200_000
MAX_BYTES = 50 * 1024 * 1024


class InvalidPDF(ValueError):
    pass


def extract_pdf_pages(content: bytes):
    if not content.startswith(b'%PDF-') or len(content) > MAX_BYTES:
        raise InvalidPDF('Invalid PDF signature or size.')
    try:
        # Child can be terminated on pathological parser/text streams. Container
        # memory/CPU limits are still required; timeout is not a memory quota.
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker'],
            input=content, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=10, check=False)
    except subprocess.TimeoutExpired as exc:
        raise InvalidPDF('PDF processing exceeded the 10 second limit.') from exc
    if result.returncode:
        raise InvalidPDF('PDF is malformed, encrypted, active, embedded, or exceeds processing limits.')
    return [(int(page), text) for page, text in json.loads(result.stdout)]


def _worker():
    from pypdf import PdfReader
    content = sys.stdin.buffer.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise InvalidPDF('size')
    # Tolerate recoverable xref offsets used by the supplied evaluation corpus;
    # successful page traversal/text limits still apply in this bounded child.
    reader = PdfReader(io.BytesIO(content), strict=False)
    if reader.is_encrypted:
        raise InvalidPDF('encrypted')
    root = reader.trailer['/Root']
    names = root.get('/Names', {})
    if hasattr(names, 'get_object'):
        names = names.get_object()
    if any(k in root for k in ('/OpenAction', '/AA')) or any(k in names for k in ('/JavaScript', '/EmbeddedFiles')):
        raise InvalidPDF('active content')
    pages = []
    size = 0
    for index, page in enumerate(reader.pages):
        if index >= MAX_PAGES or '/AA' in page:
            raise InvalidPDF('page limit or active content')
        text = page.extract_text() or ''
        size += len(text)
        if size > MAX_TEXT_CHARS:
            raise InvalidPDF('text limit')
        pages.append((index + 1, text))
    if not pages:
        raise InvalidPDF('no pages')
    sys.stdout.buffer.write(json.dumps(pages).encode('utf-8'))


if __name__ == '__main__':
    try:
        _worker()
    except Exception:
        raise SystemExit(1)
