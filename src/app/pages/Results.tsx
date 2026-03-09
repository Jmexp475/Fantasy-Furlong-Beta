import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AlertCircle } from "lucide-react";
import { SilkIcon } from "../components/Silkicon";
import { ApiNotice } from "../components/Apinotice";
import { useAppData } from "../api/Client";
import type { Runner } from "../api/Types";

function dayLabel(day: { course: string; date: string; label?: string }) {
  return day.label && day.label.trim() ? day.label : `${day.course} ${day.date}`.trim();
}

function pendingEtaText(day: any, refreshSeconds = 60): string {
  const nextRaw = day?.next_check_utc;
  if (nextRaw) {
    const nextMs = Date.parse(nextRaw);
    if (!Number.isNaN(nextMs)) {
      const mins = Math.max(1, Math.round((nextMs - Date.now()) / 60000));
      const last = day?.last_refresh ? ` Last checked ${new Date(day.last_refresh).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}.` : "";
      return `Race data not available yet. Next check in about ${mins} minute${mins === 1 ? "" : "s"}.${last}`;
    }
  }
  const mins = Math.max(1, Math.round((refreshSeconds || 60) / 60));
  return `Race data not available yet. Next check in about ${mins} minute${mins === 1 ? "" : "s"}.`;
}

function finishSortKey(runner: Runner): [number, number, string] {
  if (typeof runner.finishPosition === "number" && runner.finishPosition > 0) {
    return [0, runner.finishPosition, runner.horseName];
  }
  const statusOrder: Record<string, number> = {
    dnf: 0,
    pulled_up: 1,
    unseated: 2,
    fell: 3,
    refused: 4,
  };
  const status = String(runner.finishStatus || "").toLowerCase();
  return [1, statusOrder[status] ?? 99, runner.horseName];
}

function finishLabel(runner: Runner): string | number {
  if (typeof runner.finishPosition === "number" && runner.finishPosition > 0) return runner.finishPosition;
  const statusLabel: Record<string, string> = {
    dnf: "DNF",
    pulled_up: "PU",
    unseated: "UR",
    fell: "F",
    refused: "R",
  };
  return statusLabel[String(runner.finishStatus || "").toLowerCase()] ?? "—";
}

export default function Results() {
  const { meeting, currentDayIndex, races, picks, users, apiErrors } = useAppData();
  const raceDays = meeting?.raceDays ?? [];
  const hasDays = raceDays.length > 0;
  const [searchParams] = useSearchParams();
  const [selectedDay, setSelectedDay] = useState(currentDayIndex);
  const dayRaces = races.filter((r)=>r.dayIndex===selectedDay);
  const [activeRaceId, setActiveRaceId] = useState(searchParams.get("race") || dayRaces.find((r)=>r.status==="result")?.id || dayRaces[0]?.id);
  const activeRace = dayRaces.find((r)=>r.id===activeRaceId) ?? dayRaces[0];
  const selectedDayMeta = raceDays[selectedDay];

  if (!hasDays) {
    return <div className="p-3"><ApiNotice errors={apiErrors} /><p className="text-sm text-gray-600">No race days configured. Ask admin to edit data/racedays.json</p></div>;
  }

  return <div className="flex flex-col min-h-full"><ApiNotice errors={apiErrors} />
    <div className="flex bg-white border-b sticky top-0 z-10">{raceDays.map((d,i)=><button key={`${d.course}-${d.date}-${i}`} onClick={()=>setSelectedDay(i)} className={`flex-1 py-2 text-xs ${selectedDay===i?"bg-green-50 border-b-2 border-yellow-400":""}`}>{dayLabel(d)}<br />{d.date}</button>)}</div>
    <div className="flex overflow-x-auto bg-white border-b">{dayRaces.map((r)=><button key={r.id} onClick={()=>setActiveRaceId(r.id)} className={`px-4 py-2 text-sm ${r.id===activeRaceId?"bg-green-50 border-b-2 border-yellow-400":""}`}>{r.offTime}</button>)}</div>
    {selectedDayMeta?.status === "pending" && dayRaces.length === 0 ? <div className="p-3 text-sm text-gray-600">{pendingEtaText(selectedDayMeta, meeting?.refreshIntervalSeconds ?? 60)}</div> : null}
    {selectedDayMeta?.status === "error" && dayRaces.length === 0 ? <div className="p-3 text-sm text-red-600">{selectedDayMeta.last_error || "Racecard loading failed"}</div> : null}
    {!activeRace ? <p className="text-center py-10 text-gray-400">No races found</p> : activeRace.status !== "result" ? <div className="flex flex-col items-center py-16 text-gray-500"><AlertCircle size={28}/><p>Race not completed/results not official</p><p className="mt-1 text-xs">We aim to update the results 10 minutes after the races finish.</p></div> : <div className="p-3"><div className="bg-white rounded-lg shadow-sm overflow-hidden">{[...activeRace.runners].sort((a,b)=>{const ka = finishSortKey(a); const kb = finishSortKey(b); if (ka[0] !== kb[0]) return ka[0] - kb[0]; if (ka[1] !== kb[1]) return ka[1] - kb[1]; return ka[2].localeCompare(kb[2]);}).map((runner)=>{const pickers=picks.filter((p)=>p.runnerId===runner.id).map((p)=>users.find((u)=>u.id===p.userId)?.displayName ?? "?"); const posLabel = finishLabel(runner); return <div key={runner.id} className="grid grid-cols-[3rem_1fr_4rem_5rem] items-center px-2 py-2 border-b last:border-0"><div className="text-xs font-bold">{posLabel}</div><div className="flex items-center gap-2"><SilkIcon silkUrl={runner.silkUrl} colors={runner.silkColors} size={20}/><span className="text-xs font-semibold">{runner.horseName}</span></div><div className="text-xs font-bold text-center">{runner.pointsAwarded ?? "—"}</div><div className="text-[10px] text-center">{pickers.join(", ") || "—"}</div></div>;})}</div></div>}
  </div>;
}
