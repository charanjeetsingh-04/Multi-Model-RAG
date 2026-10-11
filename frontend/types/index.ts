export type Uuid = string;

export interface User {
  id: Uuid;
  email: string;
  username: string;
  full_name: string | null;
  is_active: boolean;
  is_admin: boolean;
  is_verified: boolean;
  created_at: string;
}

export type VideoStatus =
  | "uploaded" | "extracting_audio" | "transcribing"
  | "chunking" | "embedding" | "indexing" | "ready" | "failed";

export interface Video {
  id: Uuid;
  owner_id: Uuid;
  title: string;
  description: string | null;
  filename: string;
  mime_type: string;
  file_size_bytes: number;
  duration_seconds: number | null;
  language: string | null;
  status: VideoStatus;
  processing_error: string | null;
  processed_at: string | null;
  created_at: string;
}

export interface VideoListItem {
  id: Uuid;
  title: string;
  status: VideoStatus;
  duration_seconds: number | null;
  created_at: string;
}

export interface Citation {
  index?: number;
  chunk_id: Uuid;
  video_id: Uuid;
  score: number;
  start_time: number | null;
  end_time: number | null;
  snippet?: string | null;
}

export interface Message {
  id: Uuid;
  conversation_id: Uuid;
  role: "user" | "assistant" | "system";
  content: string;
  citations: Citation[];
  tokens_in: number | null;
  tokens_out: number | null;
  latency_ms: number | null;
  created_at: string;
}

export interface Conversation {
  id: Uuid;
  user_id: Uuid;
  video_id: Uuid | null;
  title: string;
  summary: string | null;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}
