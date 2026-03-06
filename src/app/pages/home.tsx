import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronRight, Clock, Flag, AlertCircle } from "lucide-react";
import { SilkIcon } from "../components/SilkIcon";
import { ApiNotice } from "../components/ApiNotice";
import { useAppData } from "../api/client";
import { ffTheme } from "../../theme";

function offTimeToMinutes(offTime: string): number { const [h, m] = offTime.split(":").map(Number); return h * 60 + m; }

function useCountdown(targetMinutes: number) {
  const nowMins = new Date().getUTCHours() * 60 + new Date().getUTCMinutes();
  const [remaining, setRemaining] = useState(Math.max(0, targetMinutes - nowMins));
  useEffect(() => {
    const id = setInterval(() => {
      const now = new Date().getUTCHours() * 60 + new Date().getUTCMinutes() + (new Date().getUTCSeconds() / 60);
      setRemaining(Math.max(0, targetMinutes - now));
    }, 1000);
    return () => clearInterval(id);
  }, [targetMinutes]);

  const totalSecs = Math.floor(remaining * 60);
  const hours = Math.floor(totalSecs / 3600);
  const mins = Math.floor((totalSecs % 3600) / 60);
  const secs = totalSecs % 60;
  if (hours > 0) {
    return `${String(hours).padStart(2, "0")}h ${String(mins).padStart(2, "0")}m ${String(secs).padStart(2, "0")}s`;
  }
  return `${String(mins).padStart(2, "0")}m ${String(secs).padStart(2, "0")}s`;
}

export default function Home() {
  const navigate = useNavigate();
  const { meeting, races, picks, leaderboard, currentDayIndex, currentUserId, apiErrors } = useAppData();
  const todayRaces = useMemo(() => races.filter((r) => r.dayIndex === currentDayIndex).sort((a, b) => a.offTime.localeCompare(b.offTime)), [races, currentDayIndex]);
  const selectedDayMeta = meeting?.raceDays?.[currentDayIndex];
  const nowMinutes = new Date().getUTCHours() * 60 + new Date().getUTCMinutes();
  const nextRace = todayRaces.find((r) => r.status === "declared" || (r.status === "off" && r.settled !== true));
  const myPickForNext = nextRace ? picks.find((p) => p.userId === currentUserId && p.raceId === nextRace.id) : undefined;
  const myPickRunnerForNext = myPickForNext ? nextRace?.runners.find((r) => r.id === myPickForNext.runnerId) : undefined;
  const nextRaceMinutes = nextRace ? offTimeToMinutes(nextRace.offTime) : nowMinutes + 60;
  const countdown = useCountdown(nextRaceMinutes);
  const isRaceOff = Boolean(nextRace) && (nextRace.status === "off" || nowMinutes >= nextRaceMinutes);
  const top3 = leaderboard.slice(0, 3);
  const me = leaderboard.find((l) => l.userId === currentUserId);

  return (
    <div className="p-3 flex flex-col gap-3" style={{ background: ffTheme.bg }}>
      <ApiNotice errors={apiErrors} />
      {selectedDayMeta?.status === "pending" && todayRaces.length === 0 && (
        <p className="text-sm text-gray-600">Racecards not available yet</p>
      )}
      {selectedDayMeta?.status === "error" && todayRaces.length === 0 && (
        <p className="text-sm text-red-600">{selectedDayMeta.last_error || "Racecard loading failed"}</p>
      )}
      <section className="rounded-xl p-4 text-white" style={{ background: "linear-gradient(135deg, #56309A 0%, #6F3CC8 55%, #9B6BE8 100%)", boxShadow: `0 8px 20px ${ffTheme.shadow}`, borderRadius: 18 }}>
        <div className="flex items-center justify-between mb-2">
          <span className="uppercase" style={{ fontSize: "10px", fontWeight: 700, letterSpacing: "0.1em", color: ffTheme.goldSoft }}>Next Race</span>
          <span className="px-2 py-0.5 rounded-full" style={{ fontSize: "10px", background: ffTheme.primary, color: ffTheme.white }}>{meeting?.days?.[currentDayIndex] ?? "No day"}</span>
        </div>
        {nextRace ? <>
          <h2 className="text-white mb-1" style={{ fontSize: "16px", fontWeight: 700 }}>{nextRace.raceName}</h2>
          <p className="text-green-300 mb-3" style={{ fontSize: "12px" }}>{nextRace.offTime} · {nextRace.distanceMiles} · {nextRace.fieldSize} runners</p>
          <div className="flex items-center gap-3 bg-green-800 rounded-lg p-3 mb-3">
            {myPickRunnerForNext ? <>
              <SilkIcon silkUrl={myPickRunnerForNext.silkUrl} colors={myPickRunnerForNext.silkColors} size={36} />
              <div className="flex-1 min-w-0"><p className="text-yellow-300" style={{ fontSize: "11px", fontWeight: 600 }}>Your Pick</p><p className="text-white truncate" style={{ fontSize: "14px", fontWeight: 700 }}>{myPickRunnerForNext.horseName}</p><p className="text-green-400" style={{ fontSize: "11px" }}>{myPickRunnerForNext.jockey}</p></div>
              <div className="text-right"><p className="text-yellow-400" style={{ fontSize: "10px" }}>To Win</p><p className="text-white" style={{ fontSize: "14px", fontWeight: 700 }}>{myPickRunnerForNext.pointsWin}pts</p></div>
            </> : <div className="flex items-center gap-2 flex-1"><AlertCircle size={18} className="text-yellow-400" /><p className="text-green-300" style={{ fontSize: "13px" }}>No pick made yet</p><button onClick={() => navigate(`/racecard?race=${nextRace.id}`)} className="ml-auto bg-yellow-400 text-green-900 px-3 py-1.5 rounded-lg" style={{ fontSize: "12px", fontWeight: 700 }}>Pick Now</button></div>}
          </div>
          <div className="flex items-center justify-between">
            {isRaceOff ? <span className="flex items-center gap-1.5 text-red-400" style={{ fontSize: "13px", fontWeight: 700 }}><Flag size={14} className="animate-pulse"/>Race Off</span> : <span className="flex items-center gap-1.5 text-green-300" style={{ fontSize: "13px" }}><Clock size={14}/>Begins in: <span className="text-white ml-1" style={{ fontWeight: 700 }}>{countdown}</span></span>}
            <button onClick={() => navigate(`/racecard?race=${nextRace.id}`)} className="flex items-center gap-1 bg-yellow-400 text-green-900 px-3 py-1.5 rounded-lg" style={{ fontSize: "12px", fontWeight: 700 }}>Go to Race <ChevronRight size={14}/></button>
          </div>
        </> : <p className="text-green-300 text-center py-4" style={{ fontSize: "14px" }}>All races complete for today</p>}
      </section>

      <section className="rounded-xl shadow-sm overflow-hidden" style={{ background: "#F2ECF8", border: "1px solid #E8DDF7" }}>
        <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: "#E8DDF7" }}><h3 style={{ fontSize: "13px", fontWeight: 700, color: ffTheme.text }}>Racing Dashboard</h3><div className="flex items-center gap-2"><button onClick={() => navigate("/picks")} className="flex items-center gap-1" style={{ fontSize: "11px", fontWeight: 600, color: ffTheme.primary }}>Race Picks <ChevronRight size={12}/></button><span className="px-2 py-0.5 rounded-full" style={{ fontSize: "10px", fontWeight: 600, background: ffTheme.primary, color: ffTheme.white }}>Day {currentDayIndex + 1}</span></div></div>
        {todayRaces.map((race) => {
          const pick = picks.find((p) => p.userId === currentUserId && p.raceId === race.id);
          const runner = pick ? race.runners.find((r) => r.id === pick.runnerId) : undefined;
          return <div key={race.id} className="flex items-center gap-3 px-4 py-3 border-b border-gray-100 last:border-0">
            <div className={`w-2 h-2 rounded-full ${race.status === "result" ? "bg-green-500" : race.status === "off" ? "bg-red-500 animate-pulse" : "bg-gray-300"}`}/>
            <div className="min-w-0 flex-1"><div className="flex items-center gap-2"><span className="text-green-900" style={{ fontSize: "12px", fontWeight: 700 }}>{race.offTime}</span><span className="text-gray-500 truncate" style={{ fontSize: "11px" }}>{race.raceName}</span></div>
            {runner ? <div className="flex items-center gap-1.5 mt-0.5"><SilkIcon silkUrl={runner.silkUrl} colors={runner.silkColors} size={14}/><span className="text-gray-700 truncate" style={{ fontSize: "11px" }}>{runner.horseName}</span></div> : <span className="text-gray-400" style={{ fontSize: "11px" }}>No pick</span>}</div>
            <button onClick={() => race.status === "result" ? navigate(`/results?race=${race.id}`) : navigate(`/racecard?race=${race.id}`)} className="text-green-700"><ChevronRight size={16}/></button>
          </div>;
        })}
      </section>

      <section className="rounded-xl shadow-sm overflow-hidden" style={{ background: "#F4E8B2", border: "1px solid #EBDD96" }}>
        <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: "#EBDD96" }}><h3 style={{ fontSize: "13px", fontWeight: 700, color: ffTheme.text }}>🏆 Leaderboard</h3><button onClick={() => navigate("/standings")} className="flex items-center gap-1" style={{ fontSize: "11px", fontWeight: 600, color: ffTheme.primary }}>Full Standings <ChevronRight size={12}/></button></div>
        {top3.map((entry, i) => <div key={entry.userId} className="flex items-center gap-3 px-4 py-3 border-b border-gray-100"><span className="w-7 h-7 rounded-full flex items-center justify-center text-white" style={{ fontSize: "12px", fontWeight: 700, backgroundColor: i === 0 ? "#c9a227" : i === 1 ? "#9ca3af" : "#b87333" }}>{i + 1}</span><span className="flex-1 text-gray-800" style={{ fontSize: "14px", fontWeight: 600 }}>{entry.displayName}</span><span className="text-green-700" style={{ fontSize: "14px", fontWeight: 700 }}>{entry.totalPoints}pts</span></div>)}
        {me && <div className="flex items-center gap-3 px-4 py-3 bg-green-50"><span className="w-7 h-7 rounded-full flex items-center justify-center bg-green-900 text-yellow-400" style={{ fontSize: "12px", fontWeight: 700 }}>{me.position}</span><span className="flex-1 text-green-900" style={{ fontSize: "14px", fontWeight: 700 }}>You</span><span className="text-green-700" style={{ fontSize: "14px", fontWeight: 700 }}>{me.totalPoints}pts</span></div>}
      </section>
    </div>
  );
}
