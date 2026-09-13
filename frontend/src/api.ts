export const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...options, signal: AbortSignal.timeout(120_000) });
  } catch {
    throw new Error('Backend unavailable or request timed out. Start the local backend, then retry.');
  }
  const data = await response.json();
  if (!response.ok) throw new Error(data.error?.message || 'Request failed. Please retry.');
  return data as T;
}

export interface Preview {
  transcript_name: string;
  transcript_hash: string;
  aliases: string[];
  record_count: number;
  type_counts: Record<string, number>;
  first_timestamp: string | null;
  last_timestamp: string | null;
  warnings: string[];
}
export interface Conversation {
  id: string;
  contact_id: string;
  display_name: string;
  normalized_phone: string | null;
  timezone: string;
  message_count: number;
}
export interface SavedImport {
  display_name: string;
  normalized_phone: string | null;
  import_id: string;
  contact_id: string;
  conversation_id: string;
  added_messages: number;
  duplicate_messages: number;
  chunk_count: number;
  embedding_count: number;
  provider: string;
  warnings: string[];
}
