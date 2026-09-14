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
  rag_count: number;
  first_timestamp: string | null;
  last_timestamp: string | null;
  chunk_count: number;
  embedding_count: number;
  latest_import_time: string | null;
  latest_import_status: string | null;
}
export interface ConversationDetail extends Conversation {
  participants: { alias: string; role: 'self' | 'contact' }[];
  type_counts: Record<string, number>;
  import_count: number;
  imports: { created_at: string; status: string; added_count: number; parsed_count: number | null;
    skipped_count: number | null; warnings: string[] | null }[];
  embedding_providers: { provider: string; dimensions: number; count: number }[];
}
export interface ChatMessage {
  id: string; original_text: string; original_timestamp: string | null;
  local_datetime: string | null; utc_datetime: string | null; timezone: string;
  type: string; include_in_rag: boolean; line_start: number; line_end: number;
  source_order: number; alias: string | null; role: 'self' | 'contact' | null;
}
export interface MessagePage { items: ChatMessage[]; total: number; next_offset: number | null }
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
