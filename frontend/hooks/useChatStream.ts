// SSE-based chat streaming hook.
// EventSource can't carry custom headers — so we POST to /chat/stream via
// fetch + ReadableStream, parsing SSE events manually. Works in all evergreen browsers.
import { useCallback, useRef, useState } from "react";
import { apiBaseUrl, getAccess } from "@/lib/api";
import type { Citation } from "@/types";

interface StartEvent { type: "start"; conversation_id: string; user_message_id: string; citations: Citation[]; }
interface DeltaEvent { type: "delta"; text: string; }
interface DoneEvent { type: "done"; message_id: string; conversation_id: string; citations: Citation[]; latency_ms: number; }
interface ErrorEvent { type: "error"; message: string; }
type StreamEvent = StartEvent | DeltaEvent | DoneEvent | ErrorEvent;

export interface ChatPayload {
  message: string;
  conversation_id?: string | null;
  video_id?: string | null;
  top_k?: number;
}

interface Handlers {
  onStart?: (e: StartEvent) => void;
  onDelta?: (text: string) => void;
  onDone?: (e: DoneEvent) => void;
  onError?: (msg: string) => void;
}

export function useChatStream() {
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const send = useCallback(async (payload: ChatPayload, handlers: Handlers) => {
    setStreaming(true);
    const ctl = new AbortController();
    abortRef.current = ctl;

    try {
      const res = await fetch(`${apiBaseUrl()}/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${getAccess() || ""}`,
          "Accept": "text/event-stream"
        },
        body: JSON.stringify(payload),
        signal: ctl.signal
      });
      if (!res.ok || !res.body) {
        const text = await res.text();
        handlers.onError?.(`HTTP ${res.status}: ${text.slice(0, 200)}`);
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const rawEvent = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          const dataLine = rawEvent.split("\n").find((l) => l.startsWith("data:"));
          if (!dataLine) continue;
          try {
            const ev = JSON.parse(dataLine.slice(5).trim()) as StreamEvent;
            if (ev.type === "start") handlers.onStart?.(ev);
            else if (ev.type === "delta") handlers.onDelta?.(ev.text);
            else if (ev.type === "done") handlers.onDone?.(ev);
            else if (ev.type === "error") handlers.onError?.(ev.message);
          } catch { /* skip malformed */ }
        }
      }
    } catch (e: any) {
      if (e.name !== "AbortError") handlers.onError?.(e.message);
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }, []);

  const stop = useCallback(() => abortRef.current?.abort(), []);

  return { send, stop, streaming };
}
