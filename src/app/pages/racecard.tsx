import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ChevronDown, ChevronUp, Check, Lock } from "lucide-react";
import { SilkIcon } from "../components/SilkIcon";
import { ApiNotice } from "../components/ApiNotice";
import { useAppData } from "../api/client";
import type { Runner } from "../api/types";

function HorseRow({ runner, isPicked, isLocked, onPick }: { runner: Runner; isPicked: boolean; isLocked: boolean; onPick: () => void; }) {
  const [expanded, setExpanded] = useState(false);
  const quotes = runner.quotes?.length ? runner.quotes : (runner.quote ? [runner.quote] : []);

  return (
    <div className={`border-b border-gray-100 last:border-0 ${isPicked ? "bg-green-50" : ""}`}>
      <div className="flex items-center gap-2 px-3 py-3">
        <button onClick={() => setExpanded(!expanded)} className="flex items-center gap-2 flex-1">
          <SilkIcon silkUrl={runner.silkUrl} colors={runner.silkColors} size={28} />
          <div className="text-left flex-1">
            <div className="font-bold text-sm">{runner.horseName}</div>
            <div className="text-xs text-gray-500">{runner.trainer || "—"} · {runner.jockey || "—"}</div>
            <div className="text-[11px] text-green-800">Win: {runner.pointsWin.toFixed(2)} · Place: {runner.pointsPlace.toFixed(2)}</div>
          </div>
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>
        {isLocked ? <div className="w-14 h-8 rounded bg-gray-200 flex items-center justify-center"><Lock size={12} /></div> : isPicked ? <button onClick={onPick} className="w-14 h-8 rounded bg-green-600 text-white text-xs font-bold flex items-center justify-center gap-1"><Check size={12} />Picked</button> : <button onClick={onPick} className="w-14 h-8 rounded border-2 border-green-600 text-green-700 text-xs font-bold">Pick</button>}
      </div>
      {expanded && (
        <div className="mx-3 mb-3 bg-white border rounded-xl p-3 text-xs text-gray-700 space-y-2">
          <div className="flex justify-center"><SilkIcon silkUrl={runner.silkUrl} colors={runner.silkColors} size={72} /></div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1">
            <div><span className="font-semibold">Form:</span> {runner.form || "—"}</div>
            <div><span className="font-semibold">Details:</span> {runner.details || "—"}</div>
            <div><span className="font-semibold">Trainer:</span> {runner.trainer || "—"}</div>
            <div><span className="font-semibold">Jockey:</span> {runner.jockey || "—"}</div>
            <div><span className="font-semibold">Owner:</span> {runner.owner || "—"}</div>
            <div><span className="font-semibold">Weight:</span> {runner.weight || "—"}</div>
            <div><span className="font-semibold">OR:</span> {runner.officialRating || "—"}</div>
            <div><span className="font-semibold">Breeding:</span> {runner.breeding || "—"}</div>
            <div><span className="font-semibold">Win:</span> {runner.pointsWin.toFixed(2)}</div>
            <div><span className="font-semibold">Place:</span> {runner.pointsPlace.toFixed(2)}</div>
          </div>
          <div>
            <div className="font-semibold mb-1">Quotes</div>
            {quotes.length ? quotes.map((q, i) => <p key={i}>• {q}</p>) : <p>No quotes available</p>}
          </div>
        </div>
      )}
    </div>
  );
}

export default function Racecard() {
  const [searchParams] = useSearchParams();
  const { races, currentDayIndex, picks, currentUserId, savePick, apiErrors } = useAppData();
  const dayRaces = races.filter((r) => r.dayIndex === currentDayIndex).sort((a, b) => a.offTime.localeCompare(b.offTime));
  const selectedRaceId = searchParams.get("race") ?? dayRaces[0]?.id;
  const activeRace = dayRaces.find((r) => r.id === selectedRaceId) ?? dayRaces[0];
  const isLocked = !activeRace || activeRace.status !== "declared";

  const handlePick = async (runnerId: string) => { if (!activeRace || isLocked) return; await savePick(activeRace.id, runnerId); };

  return (
    <div className="p-3 space-y-3">
      <ApiNotice errors={apiErrors} />
      {activeRace && <>
        <div className="px-4 py-3 bg-green-900 text-white"><h2 className="text-sm font-bold">{activeRace.raceName}</h2><p className="text-xs text-green-300">{activeRace.offTime} · {activeRace.distanceMiles} · {activeRace.fieldSize}</p></div>
        <div className="bg-white">{activeRace.runners.map((runner) => <HorseRow key={runner.id} runner={runner} isPicked={Boolean(picks.find((p) => p.userId === currentUserId && p.raceId === activeRace.id && p.runnerId === runner.id))} isLocked={isLocked} onPick={() => handlePick(runner.id)} />)}</div>
      </>}
    </div>
  );
}
