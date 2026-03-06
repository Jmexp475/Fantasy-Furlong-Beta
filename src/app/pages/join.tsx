import { FormEvent, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

export default function Join() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = useMemo(() => (searchParams.get("token") || "").trim(), [searchParams]);
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!token) {
      setError("Missing invite token in URL.");
      return;
    }
    const name = displayName.trim();
    if (!name) {
      setError("Display name is required.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/api/join", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, display_name: name })
      });
      if (!res.ok) {
        const body = await res.text().catch(() => "");
        throw new Error(body || `Join failed (${res.status})`);
      }
      navigate("/", { replace: true });
      window.location.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to join.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gray-50">
      <form onSubmit={onSubmit} className="w-full max-w-sm bg-white rounded-xl shadow p-4 space-y-3">
        <h1 className="text-lg font-bold text-green-900">Join Fantasy Furlong</h1>
        <p className="text-xs text-gray-600">Use your invite link to create your player session.</p>
        <div>
          <label className="text-xs text-gray-600">Invite token</label>
          <input value={token} readOnly className="w-full border rounded px-2 py-2 text-sm bg-gray-50" />
        </div>
        <div>
          <label className="text-xs text-gray-600">Display name</label>
          <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} className="w-full border rounded px-2 py-2 text-sm" placeholder="Enter name" />
        </div>
        {error ? <p className="text-xs text-red-600">{error}</p> : null}
        <button disabled={busy} className="w-full rounded px-3 py-2 text-sm font-bold bg-green-800 text-yellow-300 disabled:opacity-60">{busy ? "Joining..." : "Join"}</button>
      </form>
    </div>
  );
}
