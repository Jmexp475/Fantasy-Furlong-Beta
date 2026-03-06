import { ffTheme } from "../../theme";

export function ApiNotice({ errors }: { errors: string[] }) {
  if (!errors.length) return null;
  return (
    <div className="mx-3 mt-3 rounded-lg border p-3" style={{ background: ffTheme.goldSoft, borderColor: ffTheme.gold }}>
      <p className="text-xs font-semibold" style={{ color: ffTheme.errorText }}>API data missing/unavailable:</p>
      <ul className="mt-1 list-disc ml-4" style={{ fontSize: "11px", color: ffTheme.errorText }}>
        {errors.map((e) => <li key={e}>{e}</li>)}
      </ul>
    </div>
  );
}
