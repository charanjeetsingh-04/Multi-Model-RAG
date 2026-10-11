"use client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn, formatTime } from "@/lib/utils";
import type { Citation } from "@/types";

interface Props {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  streaming?: boolean;
}

export function MessageBubble({ role, content, citations, streaming }: Props) {
  const isUser = role === "user";
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[80%] rounded-lg px-4 py-3 text-sm",
          isUser ? "bg-primary text-primary-foreground" : "bg-card border border-border"
        )}
      >
        <div className="markdown">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content || (streaming ? "▍" : "")}</ReactMarkdown>
        </div>
        {!isUser && citations && citations.length > 0 && (
          <div className="mt-3 pt-3 border-t border-border space-y-1">
            <p className="text-xs font-semibold text-muted-foreground">Sources</p>
            {citations.map((c, i) => (
              <div key={c.chunk_id} className="text-xs text-muted-foreground">
                <span className="font-mono">[#{c.index ?? i + 1}]</span>{" "}
                {c.start_time != null && (
                  <span className="font-mono">{formatTime(c.start_time)}–{formatTime(c.end_time)}</span>
                )}
                {c.snippet && <span className="ml-2 line-clamp-2">{c.snippet}</span>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
