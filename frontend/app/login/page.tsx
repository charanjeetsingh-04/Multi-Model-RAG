"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { TokenPair, User } from "@/types";

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAuth((s) => s.setAuth);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const tokens = await api<TokenPair>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password })
      });
      // We need to set tokens BEFORE calling /auth/me
      localStorage.setItem("video_rag_access", tokens.access_token);
      localStorage.setItem("video_rag_refresh", tokens.refresh_token);
      const me = await api<User>("/auth/me");
      setAuth(me, tokens.access_token, tokens.refresh_token);
      toast.success("Welcome back");
      router.push("/dashboard");
    } catch (err: any) {
      toast.error(err.message || "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-md mx-auto px-6 py-16">
      <Card>
        <CardHeader><CardTitle>Login</CardTitle></CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={onSubmit}>
            <Input type="email" required placeholder="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            <Input type="password" required placeholder="password" value={password} onChange={(e) => setPassword(e.target.value)} />
            <Button className="w-full" disabled={loading}>{loading ? "Signing in…" : "Sign in"}</Button>
            <p className="text-sm text-muted-foreground text-center">
              No account? <Link href="/register" className="underline">Register</Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
