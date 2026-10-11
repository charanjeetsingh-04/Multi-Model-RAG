"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/store";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Upload, MessageSquare, Video } from "lucide-react";
import type { VideoListItem, Conversation } from "@/types";

export default function Dashboard() {
  const user = useAuth((s) => s.user);
  const [videos, setVideos] = useState<VideoListItem[]>([]);
  const [convs, setConvs] = useState<Conversation[]>([]);

  useEffect(() => {
    api<VideoListItem[]>("/videos").then(setVideos).catch(() => {});
    api<Conversation[]>("/chat/conversations").then(setConvs).catch(() => {});
  }, []);

  return (
    <div className="max-w-6xl mx-auto px-6 py-10 space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Welcome{user?.full_name ? `, ${user.full_name}` : ""}</h1>
        <p className="text-muted-foreground">Manage your videos and chats.</p>
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        <Link href="/upload"><Card className="hover:bg-accent transition"><CardContent className="p-6 flex items-center gap-3"><Upload/><span>Upload a video</span></CardContent></Card></Link>
        <Link href="/library"><Card className="hover:bg-accent transition"><CardContent className="p-6 flex items-center gap-3"><Video/><span>{videos.length} videos in library</span></CardContent></Card></Link>
        <Link href="/chat"><Card className="hover:bg-accent transition"><CardContent className="p-6 flex items-center gap-3"><MessageSquare/><span>{convs.length} conversations</span></CardContent></Card></Link>
      </div>

      <Card>
        <CardHeader><CardTitle>Recent videos</CardTitle></CardHeader>
        <CardContent>
          {videos.length === 0 ? (
            <p className="text-sm text-muted-foreground">No videos yet. <Link className="underline" href="/upload">Upload one</Link>.</p>
          ) : (
            <ul className="space-y-2">
              {videos.slice(0, 5).map((v) => (
                <li key={v.id} className="flex justify-between items-center text-sm">
                  <Link className="underline" href={`/chat?video=${v.id}`}>{v.title}</Link>
                  <span className="text-muted-foreground">{v.status}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
