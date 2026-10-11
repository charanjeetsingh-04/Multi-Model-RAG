"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({ email: "", username: "", password: "", full_name: "" });
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await api("/auth/register", { method: "POST", body: JSON.stringify(form) });
      toast.success("Account created. Please log in.");
      router.push("/login");
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  }

  function update<K extends keyof typeof form>(k: K, v: string) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  return (
    <div className="max-w-md mx-auto px-6 py-16">
      <Card>
        <CardHeader><CardTitle>Create your account</CardTitle></CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={onSubmit}>
            <Input required placeholder="full name" value={form.full_name} onChange={(e) => update("full_name", e.target.value)} />
            <Input required placeholder="username" value={form.username} onChange={(e) => update("username", e.target.value)} />
            <Input required type="email" placeholder="email" value={form.email} onChange={(e) => update("email", e.target.value)} />
            <Input required type="password" minLength={8} placeholder="password (min 8)" value={form.password} onChange={(e) => update("password", e.target.value)} />
            <Button className="w-full" disabled={loading}>{loading ? "Creating…" : "Create account"}</Button>
            <p className="text-sm text-muted-foreground text-center">
              Already have one? <Link href="/login" className="underline">Login</Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
