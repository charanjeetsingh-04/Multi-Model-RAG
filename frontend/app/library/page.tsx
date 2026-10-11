"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatTime } from "@/lib/utils";
import type { VideoListItem } from "@/types";
import { Trash2, MessageSquare, RefreshCw } from "lucide-react";

export default function LibraryPage() {
  const [videos, setVideos] = useState<VideoListItem[]>([]);
  const [q, setQ] = useState("");

  async function load() {
    try { setVideos(await api<VideoListItem[]>("/videos")); }
    catch (e: any) { toast.error(e.message); }
  }

  useEffect(() => {
    load();
    const i = setInterval(load, 5000);   // poll while videos are processing
    return () => clearInterval(i);
  }, []);

  async function remove(id: string) {
    if (!confirm("Delete this video?")) return;
    await api(`/videos/${id}`, { method: "DELETE" });
    toast.success("Deleted");
    load();
  }
  async function reprocess(id: string) {
    await api(`/videos/${id}/reprocess`, { method: "POST" });
    toast.success("Reprocessing started");
    load();
  }

  const filtered = videos.filter((v) => v.title.toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="max-w-4xl mx-auto px-6 py-10 space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold">Library</h1>
        <Input placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} className="max-w-xs"/>
      </div>

      {filtered.length === 0 ? (
        <p className="text-muted-foreground text-sm">No videos yet.</p>
      ) : filtered.map((v) => (
        <Card key={v.id}>
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <Link href={`/chat?video=${v.id}`} className="font-medium underline">{v.title}</Link>
              <div className="flex gap-2 mt-1 text-xs text-muted-foreground">
                <Badge>{v.status}</Badge>
                <span>{formatTime(v.duration_seconds)}</span>
                <span>{new Date(v.created_at).toLocaleString()}</span>
              </div>
            </div>
            <div className="flex gap-2">
              <Link href={`/chat?video=${v.id}`}><Button variant="outline" size="sm"><MessageSquare className="w-4 h-4"/>Chat</Button></Link>
              {v.status === "failed" && (
                <Button variant="outline" size="sm" onClick={() => reprocess(v.id)}><RefreshCw className="w-4 h-4"/>Retry</Button>
              )}
              <Button variant="destructive" size="sm" onClick={() => remove(v.id)}><Trash2 className="w-4 h-4"/></Button>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
