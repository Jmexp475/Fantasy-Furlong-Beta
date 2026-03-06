import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ChevronLeft, EyeOff } from "lucide-react";
import { ApiNotice } from "../components/ApiNotice";
import { SilkIcon } from "../components/SilkIcon";
import { useAppData } from "../api/client";
import type { Race } from "../api/types";

function offTimeToMinutes(offTime: string): number { const [h,m]=offTime.split(":").map(Number); return h*60+m; }
const nowMins = () => new Date().getUTCHours() * 60 + new Date().getUTCMinutes();

export default function OpponentView() {
  const { meeting, currentDayIndex, currentUserId, users, races, picks, leaderboard, apiErrors } = useAppData();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [selectedUserId, setSelectedUserId] = useState(searchParams.get("user") ?? users[0]?.id ?? currentUserId);
  const [selectedDay, setSelectedDay] = useState(currentDayIndex);
  const tabs = [...(meeting?.days ?? []), "Overall"];
  const isOverall = selectedDay === (meeting?.days?.length ?? 0);
  const entry = leaderboard.find((l)=>l.userId===selectedUserId);

  return <div className="flex flex-col min-h-full"><ApiNotice errors={apiErrors} />
    <div className="bg-green-900 px-4 py-3 flex items-center gap-3"><button onClick={()=>navigate('/standings')} className="text-green-300"><ChevronLeft size={22}/></button><h2 className="text-white font-bold text-sm">Opponent View</h2></div>
    <div className="bg-white p-3 border-b"><select value={selectedUserId} onChange={(e)=>setSelectedUserId(e.target.value)} className="w-full border rounded px-2 py-2 text-sm">{users.map((u)=><option key={u.id} value={u.id}>{u.displayName}</option>)}</select><p className="text-xs text-gray-500 mt-1">{entry?.totalPoints ?? 0} pts total</p></div>
    <div className="flex overflow-x-auto bg-white border-b">{tabs.map((t,i)=><button key={i} onClick={()=>setSelectedDay(i)} className={`px-4 py-2 text-xs ${selectedDay===i?"bg-green-50 border-b-2 border-yellow-400":""}`}>{t}</button>)}</div>
    <div className="p-3">{isOverall ? <div className="bg-white rounded p-3 text-sm text-gray-700">Overall summary for selected player.</div> : <div className="bg-white rounded overflow-hidden shadow-sm">{races.filter((r)=>r.dayIndex===selectedDay).map((race: Race)=>{const raceOff=nowMins()>=offTimeToMinutes(race.offTime); const hide=!raceOff && selectedUserId!==currentUserId && race.status!=="result"; const pick=picks.find((p)=>p.userId===selectedUserId && p.raceId===race.id); const runner=pick?race.runners.find((r)=>r.id===pick.runnerId):undefined; return <div key={race.id} className="grid grid-cols-[4.5rem_1fr_4rem] border-b last:border-0 items-center px-2 py-2"><div className="text-xs font-bold text-green-900">{race.offTime}</div><div className="text-xs">{hide?<span className="inline-flex items-center gap-1 text-gray-400"><EyeOff size={12}/>Hidden</span>:runner?<span className="inline-flex items-center gap-2"><SilkIcon colors={runner.silkColors} size={16}/>{runner.horseName}</span>:"No pick"}</div><div className="text-xs text-center">{runner?.pointsAwarded ?? "—"}</div></div>;})}</div>}</div>
  </div>;
}
