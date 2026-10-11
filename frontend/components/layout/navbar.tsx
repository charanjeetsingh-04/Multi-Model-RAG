"use client";
import Link from "next/link";
import { Moon, Sun, LogOut, Upload, MessageSquare, LayoutDashboard, Video } from "lucide-react";
import { useAuth, useTheme } from "@/lib/store";
import { Button } from "@/components/ui/button";

export function Navbar() {
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  const theme = useTheme((s) => s.theme);
  const toggleTheme = useTheme((s) => s.toggle);

  return (
    <header className="h-16 border-b border-border sticky top-0 z-20 bg-background/80 backdrop-blur">
      <div className="max-w-6xl mx-auto px-6 h-full flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <Video className="w-5 h-5" />
          <span>Video RAG</span>
        </Link>
        <nav className="flex items-center gap-2">
          {user && (
            <>
              <Link href="/dashboard"><Button variant="ghost" size="sm"><LayoutDashboard className="w-4 h-4"/>Dashboard</Button></Link>
              <Link href="/upload"><Button variant="ghost" size="sm"><Upload className="w-4 h-4"/>Upload</Button></Link>
              <Link href="/library"><Button variant="ghost" size="sm"><Video className="w-4 h-4"/>Library</Button></Link>
              <Link href="/chat"><Button variant="ghost" size="sm"><MessageSquare className="w-4 h-4"/>Chat</Button></Link>
            </>
          )}
          <Button variant="ghost" size="sm" onClick={toggleTheme} aria-label="toggle theme">
            {theme === "dark" ? <Sun className="w-4 h-4"/> : <Moon className="w-4 h-4"/>}
          </Button>
          {user ? (
            <Button variant="outline" size="sm" onClick={logout}><LogOut className="w-4 h-4"/>Logout</Button>
          ) : (
            <>
              <Link href="/login"><Button variant="ghost" size="sm">Login</Button></Link>
              <Link href="/register"><Button size="sm">Sign up</Button></Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
