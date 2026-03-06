import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronRight, CheckCircle2, AlertCircle } from "lucide-react";
import { SilkIcon } from "../components/SilkIcon";
import { ApiNotice } from "../components/ApiNotice";
import { useAppData } from "../api/client";

function dayLabel(day: { course: string; date: string; label?: string }) {
  return day.label && day.label.trim() ? day.label : `${day.course} ${day.date}`.trim();
}

export default function RacePicks() {
  const { meeting, currentDayIndex, currentUserId, races, picks, apiErrors } = useAppData();
  const raceDays = meeting?.raceDays ?? [];
  const hasDays = raceDays.length > 0;
  const [selectedDay, setSelectedDay] = useState(currentDayIndex);
  const navigate = useNavigate();
  const dayRaces = races.filter((r) => r.dayIndex === selectedDay);
  const selectedDayMeta = raceDays[selectedDay];

  if (!hasDays) {
    return <div className="p-3"><ApiNotice errors={apiErrors} /><p className="text-sm text-gray-600">No race days configured. Ask admin to edit data/racedays.json</p></div>;
  }

  return <div className="flex flex-col"><ApiNotice errors={apiErrors} />
    <div className="flex bg-white border-b border-gray-200 sticky top-0 z-10">
      {raceDays.map((day, i) => <button key={`${day.course}-${day.date}-${i}`} onClick={() => setSelectedDay(i)} className={`flex-1 py-3 flex flex-col items-center ${selectedDay===i?"border-b-2 border-yellow-400 bg-green-50":"text-gray-500"}`}><span style={{fontSize:"9px",fontWeight:600}} className={selectedDay===i?"text-green-900":"text-gray-400"}>{dayLabel(day)}</span><span style={{fontSize:"11px",fontWeight:700}}>{day.date}</span></button>)}
    </div>
    <div className="p-3 flex flex-col gap-2">
      {selectedDayMeta?.status === "pending" && dayRaces.length === 0 && (
        <p className="text-sm text-gray-600">Racecards not available yet</p>
      )}
      {selectedDayMeta?.status === "error" && dayRaces.length === 0 && (
        <p className="text-sm text-red-600">{selectedDayMeta.last_error || "Racecard loading failed"}</p>
      )}
      {dayRaces.map((race)=>{ const pick=picks.find((p)=>p.userId===currentUserId&&p.raceId===race.id); const runner=pick?race.runners.find((r)=>r.id===pick.runnerId):undefined; const isResult=race.status==="result"; return <button key={race.id} onClick={()=>isResult?navigate(`/results?race=${race.id}`):navigate(`/racecard?race=${race.id}`)} className="bg-white rounded-xl shadow-sm overflow-hidden text-left w-full"><div className="flex items-center justify-between px-4 py-2.5 bg-gray-50 border-b"><span className="text-green-900 font-bold text-sm">{race.offTime}</span><ChevronRight size={14}/></div><div className="px-4 py-3"><p className="text-gray-800 mb-2 text-sm font-semibold">{race.raceName}</p>{runner?<div className="flex items-center gap-3"><SilkIcon silkUrl={runner.silkUrl} colors={runner.silkColors} size={32}/><div><p className="text-sm font-bold">{runner.horseName}</p></div>{isResult?<CheckCircle2 size={18} className="text-green-500 ml-auto"/>:null}</div>:<div className="flex items-center gap-2"><AlertCircle size={16} className="text-orange-400"/><span className="text-gray-400 text-xs">No pick</span></div>}</div></button>;})}
    </div>
  </div>;
}
