"use client";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface Stats {
  users: number;
  videos: { total: number; ready: number };
  chunks: number;
  conversations: number;
  messages: number;
  vector_store_size: number;
}

export default function AdminPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [failed, setFailed] = useState<any[]>([]);

  useEffect(() => {
    api<Stats>("/admin/stats").then(setStats).catch((e) => toast.error(e.message));
    api<any[]>("/admin/failed-videos").then(setFailed).catch(() => {});
  }, []);

  return (
    <div className="max-w-5xl mx-auto px-6 py-10 space-y-4">
      <h1 className="text-2xl font-semibold">Admin</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Users" value={stats?.users}/>
        <StatCard label="Videos (ready)" value={stats ? `${stats.videos.ready}/${stats.videos.total}` : "—"}/>
        <StatCard label="Chunks" value={stats?.chunks}/>
        <StatCard label="Vectors" value={stats?.vector_store_size}/>
        <StatCard label="Conversations" value={stats?.conversations}/>
        <StatCard label="Messages" value={stats?.messages}/>
      </div>
      <Card>
        <CardHeader><CardTitle>Recent failed videos</CardTitle></CardHeader>
        <CardContent>
          {failed.length === 0 ? <p className="text-sm text-muted-foreground">None.</p> : (
            <ul className="text-sm space-y-1">
              {failed.map((v) => (
                <li key={v.id}><span className="font-mono">{v.id.slice(0, 8)}</span> {v.title}: <span className="text-red-500">{v.error}</span></li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number | string | undefined }) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-2xl font-semibold">{value ?? "—"}</p>
      </CardContent>
    </Card>
  );
}
