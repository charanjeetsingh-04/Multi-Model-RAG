"use client";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/store";

interface Pref {
  theme: string;
  language: string;
  preferred_response_style: string;
  memory_facts: Record<string, unknown>;
  notes: string | null;
}

export default function ProfilePage() {
  const user = useAuth((s) => s.user);
  const [pref, setPref] = useState<Pref | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => { api<Pref>("/users/preferences").then(setPref).catch(() => {}); }, []);

  async function save() {
    if (!pref) return;
    setLoading(true);
    try {
      const next = await api<Pref>("/users/preferences", {
        method: "PATCH",
        body: JSON.stringify({
          language: pref.language,
          preferred_response_style: pref.preferred_response_style,
          notes: pref.notes
        })
      });
      setPref(next);
      toast.success("Saved");
    } catch (e: any) { toast.error(e.message); }
    finally { setLoading(false); }
  }

  if (!pref) return <div className="p-8 text-muted-foreground">Loading…</div>;

  return (
    <div className="max-w-2xl mx-auto px-6 py-10 space-y-4">
      <Card>
        <CardHeader><CardTitle>Profile</CardTitle></CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p><span className="text-muted-foreground">Username:</span> {user?.username}</p>
          <p><span className="text-muted-foreground">Email:</span> {user?.email}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Preferences</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <Input value={pref.language} onChange={(e) => setPref({ ...pref, language: e.target.value })} placeholder="Language (e.g. en)"/>
          <Input value={pref.preferred_response_style} onChange={(e) => setPref({ ...pref, preferred_response_style: e.target.value })} placeholder="Response style"/>
          <Input value={pref.notes ?? ""} onChange={(e) => setPref({ ...pref, notes: e.target.value })} placeholder="Notes about yourself"/>
          <Button onClick={save} disabled={loading}>{loading ? "Saving…" : "Save"}</Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Long-term memory facts</CardTitle></CardHeader>
        <CardContent>
          <pre className="text-xs bg-muted rounded p-3 overflow-auto">{JSON.stringify(pref.memory_facts, null, 2)}</pre>
        </CardContent>
      </Card>
    </div>
  );
}
