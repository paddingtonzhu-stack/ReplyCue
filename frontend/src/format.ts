/** Naive export timestamps are wall-clock values, not browser-local instants. */
export function formatTimestamp(value: string | null | undefined, options: {
  timeZone?: string; wallClock?: boolean;
} = {}): string {
  if (!value) return 'Date unavailable';
  try {
    const naive = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(value);
    if (naive && !options.wallClock) return 'Date unavailable';
    const date = new Date(naive ? `${value}Z` : value);
    if (!Number.isFinite(date.getTime())) return 'Date unavailable';
    if (naive && date.toISOString().slice(0, 19) !== value.slice(0, 19)) return 'Date unavailable';
    return new Intl.DateTimeFormat(undefined, {
      year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
      timeZone: naive ? 'UTC' : options.timeZone,
    }).format(date);
  } catch { return 'Date unavailable'; }
}

export function contactLabel(contact: { display_name: string; normalized_phone?: string | null }): string {
  return contact.normalized_phone ? `${contact.display_name} · ${contact.normalized_phone}` : contact.display_name;
}
