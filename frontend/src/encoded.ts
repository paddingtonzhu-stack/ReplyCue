/** Defense for a history response from an older backend during a rolling reload. */
export function encodedMediaKind(text: string): string | null {
  if (text.length < 256) return null;
  let value = text.trim();
  if (/^data:/i.test(value)) {
    const comma = value.indexOf(',');
    if (comma < 0 || comma > 200 || !/^data:[\w.+/-]+(?:;[\w=.+-]+)*;base64$/i.test(value.slice(0, comma))) return null;
    value = value.slice(comma + 1);
  }
  // WhatsApp can append an annotation after an encoded attachment, such as
  // "<jpeg base64>: Live location: ...". Only detach a colon suffix after a
  // complete padded Base64 prefix; decoded file signatures still decide.
  const annotated = value.match(/^[A-Za-z0-9+/]+={0,2}(?=:)/);
  if (annotated) value = annotated[0];
  // Only inspect a bounded prefix for oversized legacy responses. Recognized file
  // signatures can be hidden defensively without allocating a massive decode.
  const oversized = value.length > 5 * 1024 * 1024;
  const compact = (oversized ? value.slice(0, 4096) : value).replace(/\s+/g, '');
  if (compact.length < 256 || (!oversized && (compact.length % 4 !== 0 || !/^[A-Za-z0-9+/]*={0,2}$/.test(compact)))) return null;
  try {
    const bytes = atob(oversized ? compact.slice(0, Math.floor(compact.length / 4) * 4) : compact);
    if (bytes.startsWith('\xff\xd8\xff') || bytes.startsWith('\x89PNG\r\n\x1a\n') || /^GIF8[79]a/.test(bytes) || (bytes.startsWith('RIFF') && bytes.slice(8, 12) === 'WEBP')) return 'encoded_image';
    if (bytes.startsWith('ID3') || bytes.startsWith('fLaC') || (bytes.startsWith('RIFF') && bytes.slice(8, 12) === 'WAVE')) return 'encoded_audio';
    if ((bytes.startsWith('RIFF') && bytes.slice(8, 12) === 'AVI ') || (bytes.slice(4, 8) === 'ftyp' && ['isom','iso2','mp41','mp42','avc1','qt  ','M4V '].includes(bytes.slice(8, 12)))) return 'encoded_video';
    if (bytes.startsWith('%PDF-')) return 'encoded_document';
    if (['PK\x03\x04','PK\x05\x06','PK\x07\x08'].some(prefix => bytes.startsWith(prefix))) return 'encoded_binary';
  } catch { /* Ordinary text is not encoded media. */ }
  return null;
}

export function encodedLabel(kind: string): string {
  return `${kind.replace('_', ' ').replace(/^e/, 'E')} omitted`;
}
