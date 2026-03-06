import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { AppData, LeaderboardEntry, Meeting, Pick, Race, User } from "./types";

type AppDataApi = AppData & {
  savePick: (raceId: string, runnerId: string) => Promise<void>;
};

const AppDataContext = createContext<AppDataApi | null>(null);

async function safeGet<T>(url: string): Promise<{ data: T | null; error: string | null; status: number | null }> {
  try {
    const res = await fetch(url, { credentials: "include" });
    if (!res.ok) return { data: null, error: `${url} -> ${res.status}`, status: res.status };
    return { data: (await res.json()) as T, error: null, status: res.status };
  } catch {
    return { data: null, error: `${url} -> network failure`, status: null };
  }
}

async function expectOk(url: string, init?: RequestInit): Promise<void> {
  const res = await fetch(url, { credentials: "include", ...init });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${url} -> ${res.status}${body ? `: ${body}` : ""}`);
  }
}

const EMPTY: AppData = {
  meeting: null,
  races: [],
  picks: [],
  users: [],
  leaderboard: [],
  currentUserId: "",
  currentDayIndex: 0,
  apiErrors: []
};

export function AppDataProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AppData>(EMPTY);

  useEffect(() => {
    let mounted = true;
    (async () => {
      const [me, meeting, races, picks, usersResp, leaderboard] = await Promise.all([
        safeGet<User>("/api/me"),
        safeGet<Meeting>("/api/meeting"),
        safeGet<Race[]>("/api/races"),
        safeGet<Pick[]>("/api/picks"),
        safeGet<User[]>("/api/users"),
        safeGet<LeaderboardEntry[]>("/api/leaderboard")
      ]);
      if (!mounted) return;

      const apiErrors = [meeting.error, races.error, picks.error, usersResp.error, leaderboard.error]
        .filter(Boolean) as string[];
      const m = meeting.data;
      const raceDays = m?.raceDays ?? [];
      const todayLocal = new Date().toISOString().slice(0, 10);
      const dayMatch = raceDays.findIndex((d) => d.date === todayLocal);
      const derivedDay = dayMatch >= 0 ? dayMatch : 0;

      const users = usersResp.data ?? [];
      const meUser = me.data;
      const currentUserId = meUser?.id ?? "";

      if (!meUser && me.status === 401 && !window.location.pathname.startsWith("/join")) {
        apiErrors.push("Not joined yet. Open your invite link to continue.");
      }

      setState({
        meeting: m,
        races: races.data ?? [],
        picks: picks.data ?? [],
        users,
        leaderboard: leaderboard.data ?? [],
        currentUserId,
        currentDayIndex: derivedDay,
        apiErrors
      });
    })();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    const id = setInterval(async () => {
      const lb = await safeGet<LeaderboardEntry[]>("/api/leaderboard");
      if (!lb.error && lb.data) {
        setState((s) => ({ ...s, leaderboard: lb.data }));
      }
    }, 15000);
    return () => clearInterval(id);
  }, []);

  const api = useMemo<AppDataApi>(
    () => ({
      ...state,
      savePick: async (raceId: string, runnerId: string) => {
        const userId = state.currentUserId;
        if (!userId) {
          setState((s) => ({ ...s, apiErrors: [...s.apiErrors, "No active user session. Join via invite link."] }));
          return;
        }
        setState((s) => ({
          ...s,
          picks: [...s.picks.filter((p) => !(p.userId === userId && p.raceId === raceId)), { userId, raceId, runnerId }]
        }));
        try {
          await expectOk("/api/picks", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: userId, race_id: raceId, runner_id: runnerId })
          });
        } catch {
          setState((s) => ({ ...s, apiErrors: [...s.apiErrors, "POST /api/picks -> network failure"] }));
        }
      },
    }),
    [state]
  );

  return <AppDataContext.Provider value={api}>{children}</AppDataContext.Provider>;
}

export function useAppData(): AppDataApi {
  const ctx = useContext(AppDataContext);
  if (!ctx) throw new Error("useAppData must be used inside AppDataProvider");
  return ctx;
}
