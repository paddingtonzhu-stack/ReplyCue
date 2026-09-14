"""Conservative detection of complete encoded files, never a character-set heuristic."""
import base64
import binascii
import re

MIN_ENCODED = 256
MAX_ENCODED = 5 * 1024 * 1024
KINDS = ('encoded_image','encoded_audio','encoded_video','encoded_document','encoded_binary')


def encoded_kind(text):
    if len(text) < MIN_ENCODED or len(text) > MAX_ENCODED:
        return None
    value=text.strip()
    if value[:5].lower() == 'data:':
        header, separator, value=value.partition(',')
        if not separator or len(header)>200 or not re.fullmatch(r'data:[\w.+/-]+(?:;[\w=.+-]+)*;base64',header,re.I):
            return None
    # Some WhatsApp exports append a textual attachment annotation after an
    # encoded file, for example ``<jpeg base64>: Live location: ...``.  Keep
    # the detector conservative: only detach text after a colon when the
    # prefix is itself a complete padded Base64 value.  The decoded magic-byte
    # check below still decides whether this is media.
    prefix=re.match(r'^[A-Za-z0-9+/]+={0,2}(?=:)',value)
    if prefix:
        value=prefix.group(0)
    compact=re.sub(r'\s+','',value)
    if len(compact)<MIN_ENCODED or len(compact)%4:
        return None
    try:
        decoded=base64.b64decode(compact,validate=True)
    except (ValueError,binascii.Error):
        return None
    if decoded.startswith(b'\xff\xd8\xff') or decoded.startswith(b'\x89PNG\r\n\x1a\n') or decoded.startswith((b'GIF87a',b'GIF89a')):
        return 'encoded_image'
    if decoded.startswith(b'RIFF') and decoded[8:12]==b'WEBP':return 'encoded_image'
    if decoded.startswith(b'RIFF') and decoded[8:12]==b'WAVE':return 'encoded_audio'
    if decoded.startswith((b'fLaC',b'ID3')):return 'encoded_audio'
    if decoded.startswith(b'RIFF') and decoded[8:12]==b'AVI ':return 'encoded_video'
    if decoded[4:8]==b'ftyp' and decoded[8:12] in (b'isom',b'iso2',b'mp41',b'mp42',b'avc1',b'qt  ',b'M4V '):return 'encoded_video'
    if decoded.startswith(b'%PDF-'):return 'encoded_document'
    if decoded.startswith((b'PK\x03\x04',b'PK\x05\x06',b'PK\x07\x08')):return 'encoded_binary'
    return None


def placeholder(kind):
    return kind.replace('_',' ').capitalize()+' omitted'
