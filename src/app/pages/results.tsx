import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AlertCircle } from "lucide-react";
import { SilkIcon } from "../components/SilkIcon";
import { ApiNotice } from "../components/ApiNotice";
import { useAppData } from "../api/client";

function dayLabel(day: { course: string; date: string; label?: string }) {
  return day.label && day.label.trim() ? day.label : `${day.course} ${day.date}`.trim();
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
    {selectedDayMeta?.status === "pending" && dayRaces.length === 0 ? <div className="p-3 text-sm text-gray-600">Racecards not available yet</div> : null}
    {selectedDayMeta?.status === "error" && dayRaces.length === 0 ? <div className="p-3 text-sm text-red-600">{selectedDayMeta.last_error || "Racecard loading failed"}</div> : null}
    {!activeRace ? <p className="text-center py-10 text-gray-400">No races found</p> : activeRace.status !== "result" ? <div className="flex flex-col items-center py-16 text-gray-500"><AlertCircle size={28}/><p>Race not completed / Results not official</p></div> : <div className="p-3"><div className="bg-white rounded-lg shadow-sm overflow-hidden">{[...activeRace.runners].sort((a,b)=>(a.finishPosition??999)-(b.finishPosition??999)).map((runner)=>{const pickers=picks.filter((p)=>p.runnerId===runner.id).map((p)=>users.find((u)=>u.id===p.userId)?.displayName ?? "?"); return <div key={runner.id} className="grid grid-cols-[3rem_1fr_4rem_5rem] items-center px-2 py-2 border-b last:border-0"><div className="text-xs font-bold">{runner.finishPosition ?? "DNF"}</div><div className="flex items-center gap-2"><SilkIcon silkUrl={runner.silkUrl} colors={runner.silkColors} size={20}/><span className="text-xs font-semibold">{runner.horseName}</span></div><div className="text-xs font-bold text-center">{runner.pointsAwarded ?? "—"}</div><div className="text-[10px] text-center">{pickers.join(", ") || "—"}</div></div>;})}</div></div>}
  </div>;
}
