import { BookOpen, Shield, Star } from "lucide-react";

const HOW_IT_WORKS = [
  "Pick 1 horse per race. You can change your pick until the race begins.",
  "Picks lock at the scheduled start time. After that, your choice is fixed.",
  "Score points when your horse finishes in the scoring places."
];

const RULES = [
  "4 or fewer runners: only 1st scores",
  "5–7 runners: 1st & 2nd score",
  "8–15 runners: 1st, 2nd & 3rd score",
  "16+ runners: 1st, 2nd, 3rd & 4th score"
];

const POINTS_GUIDE = [
  "Points are based on finish position and the horse’s probability of winning.",
  "Each placing has base points (higher finish = higher base points).",
  "That base score is then multiplied by a probability-based multiplier shown in the app as the horse’s Win and Place point returns.",
  "Example: If your horse wins and its Win return is 12.40 points, you score 12.40.",
  "Example: If the same horse finishes 2nd and its Place return is 6.80 points, you score 6.80.",
  "DNF penalty: If your horse does not finish, you lose 5 points for that race.",
  "NR (non-runner): If your horse is a non-runner, you score 0 and can repick before the race starts."
];

const LEADERBOARDS = [
  "Daily leaderboard shows today’s standings.",
  "Overall leaderboard totals all days."
];

const TIES = [
  "Most wins",
  "Most placings (2nd + 3rd combined)",
  "If still tied, players share the position"
];

export default function More() {
  return (
    <div className="p-3 flex flex-col gap-3">
      <section className="bg-green-900 rounded-xl p-4 text-white"><h1 className="text-yellow-400 font-bold">Fantasy Furlong</h1><p className="text-green-300 text-xs">How Fantasy Furlong Works</p></section>

      <section className="bg-white rounded-xl shadow-sm overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-3 bg-gray-50 border-b"><BookOpen size={16} className="text-green-700"/><h2 className="text-green-900 text-sm font-bold">How it works</h2></div>
        <div className="p-4">{HOW_IT_WORKS.map((row) => <p key={row} className="text-xs text-gray-600 mb-1">• {row}</p>)}</div>
      </section>

      <section className="bg-white rounded-xl shadow-sm overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-3 bg-gray-50 border-b"><Shield size={16} className="text-green-700"/><h2 className="text-green-900 text-sm font-bold">Rules</h2></div>
        <div className="p-4">{RULES.map((r) => <p key={r} className="text-xs text-gray-600 mb-1">• {r}</p>)}</div>
      </section>

      <section className="bg-white rounded-xl shadow-sm overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-3 bg-gray-50 border-b"><Star size={16} className="text-green-700"/><h2 className="text-green-900 text-sm font-bold">Points guide</h2></div>
        <div className="p-4">{POINTS_GUIDE.map((row) => <p key={row} className="text-xs text-gray-600 mb-1">• {row}</p>)}</div>
      </section>

      <section className="bg-white rounded-xl shadow-sm overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-3 bg-gray-50 border-b"><BookOpen size={16} className="text-green-700"/><h2 className="text-green-900 text-sm font-bold">Leaderboards</h2></div>
        <div className="p-4">{LEADERBOARDS.map((row) => <p key={row} className="text-xs text-gray-600 mb-1">• {row}</p>)}</div>
      </section>

      <section className="bg-white rounded-xl shadow-sm overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-3 bg-gray-50 border-b"><Shield size={16} className="text-green-700"/><h2 className="text-green-900 text-sm font-bold">Ties</h2></div>
        <div className="p-4">{TIES.map((row) => <p key={row} className="text-xs text-gray-600 mb-1">• {row}</p>)}</div>
      </section>
    </div>
  );
}
