import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import { ApiNotice } from "../components/ApiNotice";
import { useAppData } from "../api/client";

function dayLabel(day: { course: string; date: string; label?: string }) {
  return day.label && day.label.trim() ? day.label : `${day.course} (${day.date})`;
}

export default function Standings() {
  const { meeting, currentDayIndex, currentUserId, leaderboard, apiErrors } = useAppData();
  const raceDays = meeting?.raceDays ?? [];
  const hasDays = raceDays.length > 0;
  const [selectedTab, setSelectedTab] = useState(currentDayIndex);
  const navigate = useNavigate();

  if (!hasDays) {
    return <div className="p-3"><ApiNotice errors={apiErrors} /><p className="text-sm text-gray-600">No race days configured. Ask admin to edit data/racedays.json</p></div>;
  }

  const tabs = [...raceDays.map((d) => dayLabel(d)), "Overall"];
  const isOverall = selectedTab === raceDays.length;
  const sorted = [...leaderboard].sort((a,b)=> (isOverall ? b.totalPoints-a.totalPoints : (b.dayPoints[selectedTab]??0)-(a.dayPoints[selectedTab]??0)));
  const selectedDayMeta = raceDays[selectedTab];

  return <div className="flex flex-col min-h-full"><ApiNotice errors={apiErrors} />
    <div className="flex overflow-x-auto bg-white border-b sticky top-0 z-10">{tabs.map((t,i)=><button key={i} onClick={()=>setSelectedTab(i)} className={`px-4 py-2 text-xs ${selectedTab===i?"bg-green-50 border-b-2 border-yellow-400":""}`}>{t}</button>)}</div>
    {!isOverall && selectedDayMeta?.status === "pending" ? <div className="p-3 text-sm text-gray-600">Racecards not available yet</div> : null}
    {!isOverall && selectedDayMeta?.status === "error" ? <div className="p-3 text-sm text-red-600">{selectedDayMeta.last_error || "Racecard loading failed"}</div> : null}
    <div className="p-3"><div className="bg-white rounded-lg overflow-hidden shadow-sm">{sorted.map((e,i)=>{ const pts = isOverall?e.totalPoints:(e.dayPoints[selectedTab]??0); const isMe=e.userId===currentUserId; return <button key={e.userId} onClick={()=>navigate(`/opponent?user=${e.userId}`)} className={`w-full flex items-center gap-3 px-3 py-3 border-b last:border-0 ${isMe?"bg-green-50":""}`}><span className="w-6 text-center text-xs font-bold">{i+1}</span><span className="flex-1 text-left text-sm font-semibold">{e.displayName}{isMe?" (You)":""}</span><span className="text-sm font-bold text-green-700">{pts}pts</span><ChevronRight size={14} className="text-gray-400"/></button>;})}</div></div>
  </div>;
}
