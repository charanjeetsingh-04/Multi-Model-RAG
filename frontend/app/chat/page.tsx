"use client";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { Send, StopCircle } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MessageBubble } from "@/components/chat/message-bubble";
import { useChatStream } from "@/hooks/useChatStream";
import type { Citation, Conversation, ConversationDetail, Message, VideoListItem } from "@/types";

interface UiMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  streaming?: boolean;
}

export default function ChatPage() {
  const params = useSearchParams();
  const videoIdFromUrl = params.get("video");
  const [videos, setVideos] = useState<VideoListItem[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedVideoId, setSelectedVideoId] = useState<string | null>(videoIdFromUrl);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const { send, stop, streaming } = useChatStream();
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    api<VideoListItem[]>("/videos").then(setVideos).catch(() => {});
    api<Conversation[]>("/chat/conversations").then(setConversations).catch(() => {});
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function openConversation(id: string) {
    const detail = await api<ConversationDetail>(`/chat/conversations/${id}`);
    setConversationId(detail.id);
    setSelectedVideoId(detail.video_id);
    setMessages(
      detail.messages.map((m: Message) => ({
        id: m.id, role: m.role === "assistant" ? "assistant" : "user",
        content: m.content, citations: m.citations as Citation[]
      }))
    );
  }

  function newConversation() {
    setConversationId(null);
    setMessages([]);
  }

  async function onSend() {
    const text = input.trim();
    if (!text || streaming) return;
    setInput("");

    const userMsg: UiMessage = { id: crypto.randomUUID(), role: "user", content: text };
    const placeholderId = crypto.randomUUID();
    const placeholder: UiMessage = { id: placeholderId, role: "assistant", content: "", streaming: true, citations: [] };
    setMessages((m) => [...m, userMsg, placeholder]);

    await send(
      {
        message: text,
        conversation_id: conversationId,
        video_id: selectedVideoId,
      },
      {
        onStart: (e) => {
          setConversationId(e.conversation_id);
          setMessages((m) => m.map((x) => x.id === placeholderId ? { ...x, citations: e.citations } : x));
        },
        onDelta: (delta) => {
          setMessages((m) =>
            m.map((x) => x.id === placeholderId ? { ...x, content: x.content + delta } : x)
          );
        },
        onDone: (e) => {
          setMessages((m) =>
            m.map((x) => x.id === placeholderId ? { ...x, streaming: false, citations: e.citations } : x)
          );
          // refresh conversation list
          api<Conversation[]>("/chat/conversations").then(setConversations).catch(() => {});
        },
        onError: (msg) => {
          toast.error(msg);
          setMessages((m) =>
            m.map((x) => x.id === placeholderId ? { ...x, streaming: false, content: x.content || "_(error)_" } : x)
          );
        }
      }
    );
  }

  return (
    <div className="max-w-6xl mx-auto h-[calc(100vh-4rem)] grid grid-cols-12 gap-4 p-4">
      {/* Sidebar */}
      <aside className="col-span-3 border border-border rounded-lg p-3 overflow-y-auto space-y-3">
        <Button className="w-full" onClick={newConversation}>+ New chat</Button>
        <div>
          <p className="text-xs uppercase text-muted-foreground mb-2">Scope</p>
          <select
            className="w-full bg-background border border-border rounded p-2 text-sm"
            value={selectedVideoId || ""}
            onChange={(e) => setSelectedVideoId(e.target.value || null)}
          >
            <option value="">All my videos</option>
            {videos.filter((v) => v.status === "ready").map((v) => (
              <option key={v.id} value={v.id}>{v.title}</option>
            ))}
          </select>
        </div>
        <div>
          <p className="text-xs uppercase text-muted-foreground mb-2">Conversations</p>
          <div className="space-y-1">
            {conversations.map((c) => (
              <button
                key={c.id}
                onClick={() => openConversation(c.id)}
                className={`w-full text-left text-sm p-2 rounded hover:bg-accent ${c.id === conversationId ? "bg-accent" : ""}`}
              >
                {c.title}
              </button>
            ))}
          </div>
        </div>
      </aside>

      {/* Conversation pane */}
      <section className="col-span-9 flex flex-col border border-border rounded-lg">
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.length === 0 && (
            <div className="text-center text-muted-foreground text-sm pt-20">
              Ask a question about your videos.
            </div>
          )}
          {messages.map((m) => (
            <MessageBubble key={m.id} role={m.role} content={m.content} citations={m.citations} streaming={m.streaming} />
          ))}
        </div>
        <div className="p-3 border-t border-border flex gap-2">
          <Input
            placeholder="Ask anything…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) onSend(); }}
            disabled={streaming}
          />
          {streaming ? (
            <Button variant="outline" onClick={stop}><StopCircle className="w-4 h-4"/></Button>
          ) : (
            <Button onClick={onSend}><Send className="w-4 h-4"/></Button>
          )}
        </div>
      </section>
    </div>
  );
}
