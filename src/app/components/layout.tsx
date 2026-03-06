import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { Home, Binoculars, ListOrdered, Trophy, MoreHorizontal, ClipboardList } from "lucide-react";
import { useAppData } from "../api/client";
import { ffTheme } from "../../theme";

const NAV_ITEMS = [
  { path: "/", label: "Home", Icon: Home },
  { path: "/picks", label: "Race Picks", Icon: Binoculars },
  { path: "/racecard", label: "Racecard", Icon: ClipboardList },
  { path: "/results", label: "Results", Icon: ListOrdered },
  { path: "/standings", label: "Standings", Icon: Trophy },
  { path: "/more", label: "More", Icon: MoreHorizontal }
];

export function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { users, currentUserId } = useAppData();
  const currentUser = users.find((u) => u.id === currentUserId);
  const badge = (currentUser?.displayName?.trim()?.[0] ?? "?").toUpperCase();

  return (
    <div className="flex flex-col min-h-screen max-w-md mx-auto relative" style={{ background: ffTheme.bg }}>
      <header className="sticky top-0 z-50" style={{ background: ffTheme.surface, borderBottom: `1px solid ${ffTheme.border}` }}>
        <div className="flex items-center gap-3 px-4 py-3">
          <img src="/logo.png" alt="Fantasy Furlong" style={{ width: 36, height: 36, borderRadius: 8, objectFit: "cover", boxShadow: `0 4px 10px ${ffTheme.shadow}` }} />
          <div>
            <h1 style={{ fontSize: "15px", fontWeight: 700, letterSpacing: "0.08em", lineHeight: 1.1, color: ffTheme.text }}>FANTASY FURLONG</h1>
            <p style={{ fontSize: "11px", letterSpacing: "0.04em", color: ffTheme.textMuted }}>Cheltenham Festival 2026</p>
          </div>
          <div className="ml-auto"><div className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold" style={{ background: ffTheme.gold, color: ffTheme.primaryDark }}>{badge}</div></div>
        </div>
      </header>
      <main className="flex-1 overflow-y-auto pb-20"><Outlet /></main>
      <nav className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-md z-50 shadow-[0_-2px_12px_rgba(0,0,0,0.08)]" style={{ background: ffTheme.navBg, borderTop: `1px solid ${ffTheme.border}` }}>
        <div className="flex items-center justify-around py-1">
          {NAV_ITEMS.map(({ path, label, Icon }) => {
            const active = location.pathname === path || (path !== "/" && location.pathname.startsWith(path));
            return <button key={path} onClick={() => navigate(path)} className="flex flex-col items-center gap-0.5 px-2 py-2 min-w-0 flex-1"><Icon size={20} color={active ? ffTheme.primary : ffTheme.textMuted} /><span style={{ fontSize: "9px", fontWeight: active ? 700 : 500, lineHeight: 1.2, color: active ? ffTheme.primary : ffTheme.textMuted }}>{label}</span></button>;
          })}
        </div>
      </nav>
    </div>
  );
}
