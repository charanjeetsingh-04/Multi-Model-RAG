// Global state — Zustand. Just auth + theme; chat owns its own local state.
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "@/types";
import { clearTokens, setTokens } from "@/lib/api";

interface AuthState {
  user: User | null;
  hydrated: boolean;
  setUser: (u: User | null) => void;
  setAuth: (u: User, access: string, refresh: string) => void;
  logout: () => void;
  setHydrated: () => void;
}

export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      hydrated: false,
      setUser: (u) => set({ user: u }),
      setAuth: (user, access, refresh) => {
        setTokens(access, refresh);
        set({ user });
      },
      logout: () => {
        clearTokens();
        set({ user: null });
      },
      setHydrated: () => set({ hydrated: true })
    }),
    {
      name: "video-rag-auth",
      onRehydrateStorage: () => (state) => state?.setHydrated()
    }
  )
);

interface ThemeState {
  theme: "light" | "dark";
  toggle: () => void;
}
export const useTheme = create<ThemeState>()(
  persist(
    (set, get) => ({
      theme: "dark",
      toggle: () => set({ theme: get().theme === "dark" ? "light" : "dark" })
    }),
    { name: "video-rag-theme" }
  )
);
