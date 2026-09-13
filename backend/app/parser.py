"""Bounded, in-memory parsing. Archive text is data, never executable instructions."""
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from io import BytesIO
from pathlib import PurePosixPath
import re
import stat
import unicodedata
import zipfile

MAX_ZIP = 10 * 1024 * 1024
MAX_TEXT = 5 * 1024 * 1024
MAX_TOTAL = 30 * 1024 * 1024
MAX_ENTRIES = 100
HEADER = re.compile(r'^\[(\d{1,2}/\d{1,2}/\d{2}),\s+(\d{1,2}:\d{2}:\d{2}\s+[AP]M)\]\s?(.*)$')


class ImportProblem(Exception):
    def __init__(self, code, message, status=400):
        self.code, self.message, self.status = code, message, status


@dataclass
class Message:
    sender: str | None
    timestamp: str | None
    local_datetime: str | None
    text: str
    kind: str
    line_start: int
    line_end: int


@dataclass
class Parsed:
    transcript_name: str
    archive_hash: str
    transcript_hash: str
    messages: list[Message]
    warnings: list[str]

    @property
    def aliases(self):
        return sorted({m.sender for m in self.messages if m.sender is not None})

    def preview(self):
        dates = [m.local_datetime for m in self.messages if m.local_datetime]
        return dict(transcript_name=self.transcript_name, transcript_hash=self.transcript_hash,
                    aliases=self.aliases, record_count=len(self.messages),
                    type_counts=dict(Counter(m.kind for m in self.messages)),
                    first_timestamp=min(dates) if dates else None,
                    last_timestamp=max(dates) if dates else None, warnings=self.warnings,
                    encoding='UTF-8', timestamp_format='M/D/YY, h:mm:ss AM/PM',
                    timezone_in_source=False)


def normalize(text):
    # Keep original text separately; do not strip emoji, ZWJ, or variation selectors.
    return ' '.join(unicodedata.normalize('NFC', text).split())


def classify(text, sender):
    value = text.strip().casefold()
    if value in ('[call]', '- [call]') or re.fullmatch(r'(?:missed )?(?:voice|video) call(?:,.*)?', value):
        return 'call'
    if 'end-to-end encrypted' in value or value.startswith('messages and calls are end-to-end'):
        return 'system'
    if re.fullmatch(r'(?:this message was deleted|you deleted this message)[.!]?', value):
        return 'deleted'
    match = re.fullmatch(r'[<\[]?(voice message|image|video|audio|sticker|document|gif|media) omitted[>\]]?', value)
    if match:
        return {'voice message': 'voice', 'media': 'unknown'}.get(match[1], match[1])
    if not value or sender is None or re.fullmatch(r'[<\[].*[>\]]', value):
        return 'unknown'
    return 'text'


def read_export(data: bytes, transcript_name: str | None = None) -> Parsed:
    if not data or len(data) > MAX_ZIP:
        raise ImportProblem('archive_size', 'Choose a ZIP no larger than 10 MB.', 413)
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > MAX_ENTRIES:
                raise ImportProblem('entry_count', 'ZIP must contain 1–100 entries.')
            total, names, transcripts = 0, set(), []
            for entry in entries:
                name = entry.filename
                parts = PurePosixPath(name).parts
                if (not name or '\x00' in entry.orig_filename or '\\' in entry.orig_filename or '\\' in name or ':' in name or name.startswith('/')
                    or any(p in ('..', '.') for p in name.split('/'))
                    or any(ord(c) < 32 for c in name) or any(p.endswith((' ', '.')) for p in parts)
                    or stat.S_ISLNK(entry.external_attr >> 16)):
                    raise ImportProblem('unsafe_path', 'ZIP contains an unsafe entry path.')
                if name.casefold() in names:
                    raise ImportProblem('duplicate_entry', 'ZIP contains duplicate entry names.')
                names.add(name.casefold())
                if entry.flag_bits & 1:
                    raise ImportProblem('encrypted_entry', 'Encrypted ZIP entries are not supported.')
                total += entry.file_size
                if total > MAX_TOTAL or entry.file_size > MAX_TOTAL or entry.file_size / max(entry.compress_size, 1) > 100:
                    raise ImportProblem('archive_expansion', 'ZIP exceeds safe expansion limits.', 413)
                if not entry.is_dir() and name.lower().endswith('.txt'):
                    transcripts.append(name)
            if transcript_name:
                if transcript_name not in transcripts:
                    raise ImportProblem('transcript_missing', 'Selected transcript is not in this ZIP.')
            elif len(transcripts) == 1:
                transcript_name = transcripts[0]
            else:
                preferred = [n for n in transcripts if PurePosixPath(n).name.lower() in ('chat.txt', '_chat.txt')]
                if len(preferred) != 1:
                    raise ImportProblem('transcript_ambiguous', 'ZIP must contain one text transcript or one uniquely named chat.txt/_chat.txt.')
                transcript_name = preferred[0]
            entry = archive.getinfo(transcript_name)
            if entry.file_size > MAX_TEXT:
                raise ImportProblem('transcript_size', 'Transcript must be no larger than 5 MB.', 413)
            with archive.open(entry) as handle:
                raw = handle.read(MAX_TEXT + 1)
            if len(raw) > MAX_TEXT:
                raise ImportProblem('transcript_size', 'Transcript exceeds 5 MB.', 413)
    except ImportProblem:
        raise
    except (zipfile.BadZipFile, OSError, RuntimeError, NotImplementedError, EOFError):
        raise ImportProblem('invalid_zip', 'Cannot read this ZIP archive.') from None
    try:
        text = raw.decode('utf-8-sig', errors='strict')
    except UnicodeDecodeError:
        raise ImportProblem('encoding', 'Transcript is not valid UTF-8. Export it again; no replacement or encoding guesses were applied.') from None
    warnings = ['Timestamps have no timezone. Confirm the export timezone before importing.']
    if '\ufffd' in text:
        warnings.append(f'Source contains {text.count(chr(0xfffd))} replacement characters; original source loss is preserved.')
    messages, current = [], None
    lines = text.splitlines()
    if len(lines) > 100_000:
        raise ImportProblem('record_limit', 'Transcript has too many lines.', 413)
    for number, line in enumerate(lines, 1):
        match = HEADER.match(line.lstrip('\ufeff\u200e\u200f'))
        if match:
            if current:
                messages.append(current)
            date, time, body = match.groups()
            stamp = f'{date}, {time}'
            try:
                # Explicit contemporary two-digit-year policy, independent of strptime's pivot.
                month, day, year = map(int, date.split('/'))
                parsed_time = datetime.strptime(time, '%I:%M:%S %p').time()
                local = datetime.combine(datetime(2000 + year, month, day).date(), parsed_time).isoformat()
            except ValueError:
                raise ImportProblem('timestamp', f'Invalid timestamp at line {number}.') from None
            sender = None
            if not body.startswith('- ') and ': ' in body:
                sender, body = body.split(': ', 1)
                if not sender.strip() or len(sender) > 200:
                    raise ImportProblem('alias', f'Invalid sender label at line {number}.')
            current = Message(sender, stamp, local, body, '', number, number)
        else:
            if current:
                current.text += '\n' + line
                current.line_end = number
            elif line.strip():
                current = Message(None, None, None, line, '', number, number)
    if current:
        messages.append(current)
    if not any(m.timestamp for m in messages):
        raise ImportProblem('format', 'No supported [M/D/YY, h:mm:ss AM/PM] message headers found.')
    for message in messages:
        message.kind = classify(message.text, message.sender)
    if len(messages) > 50_000:
        raise ImportProblem('record_limit', 'Transcript has too many records.', 413)
    warnings.append('Two-digit years are interpreted as 2000–2099. Review the displayed date range.')
    return Parsed(transcript_name, sha256(data).hexdigest(), sha256(raw).hexdigest(), messages, warnings)
