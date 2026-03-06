import { useEffect, useMemo, useState } from "react";

type Tab = "Status" | "Refresh" | "Races" | "Results" | "Upload" | "Invites";

async function api<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { credentials: "include", ...init });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${text}`);
  }
  return (await res.json()) as T;
}

function dateOptions(): string[] {
  const now = new Date();
  return Array.from({ length: 9 }, (_, i) => {
    const d = new Date(now);
    d.setDate(now.getDate() + i);
    return d.toISOString().slice(0, 10);
  });
}

export default function Admin() {
  const [authed, setAuthed] = useState(false);
  const [pwd, setPwd] = useState("");
  const [tab, setTab] = useState<Tab>("Status");
  const [msg, setMsg] = useState("");
  const [health, setHealth] = useState<any>(null);
  const [logRows, setLogRows] = useState<string[]>([]);
  const opts = useMemo(() => dateOptions(), []);
  const [date, setDate] = useState(opts[0]);
  const [races, setRaces] = useState<any[]>([]);
  const [selectedRace, setSelectedRace] = useState("");
  const [runners, setRunners] = useState<any[]>([]);
  const [first, setFirst] = useState("");
  const [second, setSecond] = useState("");
  const [third, setThird] = useState("");
  const [fourth, setFourth] = useState("");
  const [dnf, setDnf] = useState("");
  const [nr, setNr] = useState("");
  const [preview, setPreview] = useState<any>(null);
  const [invites, setInvites] = useState<any[]>([]);
  const [inviteCount, setInviteCount] = useState(5);
  const [inviteHours, setInviteHours] = useState(48);

  useEffect(() => {
    api<{ ok: boolean }>("/api/admin/session").then(() => setAuthed(true)).catch(() => setAuthed(false));
  }, []);

  useEffect(() => {
    if (!authed) return;
    const load = () => api<any>("/health").then(setHealth).catch((e) => setMsg(String(e)));
    load();
    const id = setInterval(load, 10000);
    return () => clearInterval(id);
  }, [authed]);

  async function login() {
    try {
      await api("/api/admin/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ password: pwd }) });
      setAuthed(true);
      setMsg("Logged in.");
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  async function runRefresh(kind: string) {
    try {
      const data = await api(`/api/admin/refresh/${kind}`, { method: "POST" });
      setLogRows((p) => [`${new Date().toISOString()} ${JSON.stringify(data)}`, ...p]);
    } catch (e) {
      setLogRows((p) => [`${new Date().toISOString()} ERROR ${(e as Error).message}`, ...p]);
    }
  }

  async function loadRaces() {
    try {
      const rows = await api<any[]>(`/api/admin/races?date=${date}`);
      setRaces(rows);
      setMsg(`Loaded ${rows.length} races`);
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  async function lockRace(raceId: string, locked: boolean) {
    try {
      await api("/api/admin/race/lock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ race_id: raceId, locked, confirm: !locked })
      });
      await loadRaces();
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  async function loadRunners(raceId: string) {
    setSelectedRace(raceId);
    const rows = await api<any[]>(`/api/admin/race/${raceId}/runners`);
    setRunners(rows);
  }

  async function saveProvisional() {
    try {
      await api(`/api/admin/race/${selectedRace}/results/provisional`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ first, second, third, fourth, dnf_ids: dnf ? dnf.split(",").map((x) => x.trim()).filter(Boolean) : [], nr_ids: nr ? nr.split(",").map((x) => x.trim()).filter(Boolean) : [] })
      });
      setMsg("Provisional saved");
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  async function confirmOfficial() {
    try {
      await api(`/api/admin/race/${selectedRace}/results/confirm_official`, { method: "POST" });
      setMsg("Official confirmed");
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  async function uploadFile(file: File) {
    const fd = new FormData();
    fd.append("file", file);
    try {
      const data = await api("/api/admin/upload/racecard_xlsx", { method: "POST", body: fd });
      setPreview(data);
    } catch (e) {
      setMsg((e as Error).message);
    }
  }

  async function loadInvites() {
    const rows = await api<any[]>("/api/admin/invites/list");
    setInvites(rows);
  }

  if (!authed) {
    return (
      <div className="max-w-md mx-auto mt-20 p-4 bg-white rounded shadow">
        <h1 className="font-bold text-lg mb-3">Admin Login</h1>
        <input type="password" value={pwd} onChange={(e) => setPwd(e.target.value)} className="w-full border rounded px-3 py-2" placeholder="Admin password" />
        <button onClick={login} className="mt-3 bg-green-800 text-yellow-400 px-4 py-2 rounded">Login</button>
        {msg ? <p className="text-red-600 text-sm mt-2">{msg}</p> : null}
      </div>
    );
  }

  return (
    <div className="p-4 max-w-5xl mx-auto">
      <h1 className="text-xl font-bold text-green-900">Admin Console</h1>
      {msg ? <p className="text-sm text-red-600 mt-1">{msg}</p> : null}
      <div className="flex gap-2 flex-wrap mt-3">
        {(["Status", "Refresh", "Races", "Results", "Upload", "Invites"] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`px-3 py-1 rounded border ${tab === t ? "bg-green-900 text-yellow-400" : "bg-white"}`}>{t}</button>
        ))}
      </div>

      {tab === "Status" ? <section className="mt-4 bg-white rounded p-4 border"><pre className="text-xs whitespace-pre-wrap">{JSON.stringify(health, null, 2)}</pre><button onClick={() => api("/api/admin/cache/clear", { method: "POST" }).then(() => setMsg("Cache cleared")).catch((e) => setMsg((e as Error).message))} className="mt-2 border px-3 py-1 rounded">Clear cache</button></section> : null}

      {tab === "Refresh" ? <section className="mt-4 bg-white rounded p-4 border"><div className="flex gap-2 flex-wrap"><button onClick={() => runRefresh("racecards")} className="border px-3 py-1 rounded">Refresh racecards</button><button onClick={() => runRefresh("odds")} className="border px-3 py-1 rounded">Refresh odds</button><button onClick={() => runRefresh("results")} className="border px-3 py-1 rounded">Refresh results</button><button onClick={() => runRefresh("full")} className="border px-3 py-1 rounded">Refresh full</button></div><div className="mt-3 max-h-56 overflow-auto bg-gray-50 p-2 text-xs">{logRows.map((r, i) => <div key={i}>{r}</div>)}</div></section> : null}

      {tab === "Races" ? <section className="mt-4 bg-white rounded p-4 border"><div className="flex gap-2"><select value={date} onChange={(e) => setDate(e.target.value)} className="border rounded px-2 py-1">{opts.map((o) => <option key={o}>{o}</option>)}</select><button onClick={loadRaces} className="border px-3 py-1 rounded">Load races</button></div><div className="mt-3 space-y-2">{races.map((r) => <div key={r.race_id} className="border rounded p-2 text-sm"><div className="font-semibold">{r.off_time} {r.race_name}</div><div className="text-xs text-gray-600">{r.race_status} · locked={String(r.locked)} · settled={String(r.settled)}</div><div className="flex gap-2 mt-1"><button onClick={() => lockRace(r.race_id, true)} className="border px-2 py-1 rounded">Lock</button><button onClick={() => lockRace(r.race_id, false)} className="border px-2 py-1 rounded">Unlock</button><button onClick={() => api("/api/admin/race/force_settle", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ race_id: r.race_id }) }).then(() => setMsg("Settled")).catch((e) => setMsg((e as Error).message))} className="border px-2 py-1 rounded">Force settle</button></div></div>)}</div></section> : null}

      {tab === "Results" ? <section className="mt-4 bg-white rounded p-4 border"><div className="flex gap-2"><button onClick={loadRaces} className="border px-3 py-1 rounded">Load races</button><select value={selectedRace} onChange={(e) => loadRunners(e.target.value)} className="border rounded px-2 py-1"><option value="">Select race</option>{races.map((r) => <option key={r.race_id} value={r.race_id}>{r.off_time} {r.race_name}</option>)}</select></div><div className="grid grid-cols-2 gap-2 mt-3">{[first, second, third, fourth].map((v, i) => <select key={i} value={v} onChange={(e) => [setFirst, setSecond, setThird, setFourth][i](e.target.value)} className="border rounded px-2 py-1"><option value="">{i + 1} place</option>{runners.map((r) => <option key={r.horse_id} value={r.horse_id}>{r.horse_name}</option>)}</select>)}</div><input value={dnf} onChange={(e) => setDnf(e.target.value)} placeholder="DNF IDs (comma)" className="mt-2 border rounded px-2 py-1 w-full"/><input value={nr} onChange={(e) => setNr(e.target.value)} placeholder="NR IDs (comma)" className="mt-2 border rounded px-2 py-1 w-full"/><div className="mt-2 flex gap-2"><button onClick={saveProvisional} className="border px-3 py-1 rounded">Save provisional</button><button onClick={confirmOfficial} className="border px-3 py-1 rounded">Confirm official</button></div></section> : null}

      {tab === "Upload" ? <section className="mt-4 bg-white rounded p-4 border"><input type="file" accept=".xlsx" onChange={(e) => { const f = e.target.files?.[0]; if (f) void uploadFile(f); }} /><button onClick={() => api("/api/admin/upload/commit", { method: "POST" }).then(() => setMsg("Import committed")).catch((e) => setMsg((e as Error).message))} className="ml-2 border px-3 py-1 rounded">Commit import</button>{preview ? <pre className="mt-3 text-xs bg-gray-50 p-2">{JSON.stringify(preview, null, 2)}</pre> : null}</section> : null}

      {tab === "Invites" ? <section className="mt-4 bg-white rounded p-4 border"><div className="flex gap-2 items-center"><input type="number" value={inviteCount} onChange={(e) => setInviteCount(Number(e.target.value))} className="border rounded px-2 py-1 w-24"/><input type="number" value={inviteHours} onChange={(e) => setInviteHours(Number(e.target.value))} className="border rounded px-2 py-1 w-24"/><button onClick={() => api("/api/admin/invites/create", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ count: inviteCount, expires_hours: inviteHours }) }).then(loadInvites).catch((e) => setMsg((e as Error).message))} className="border px-3 py-1 rounded">Create</button><button onClick={loadInvites} className="border px-3 py-1 rounded">Reload</button></div><div className="mt-3 space-y-2 text-xs">{invites.map((i) => <div key={i.token} className="border rounded p-2"><div>token: {i.token}</div><div>join link: http://localhost:5173/join?token={i.token}</div><button onClick={() => navigator.clipboard.writeText(`http://localhost:5173/join?token=${i.token}`)} className="mr-2 border px-2 py-1 rounded">Copy link</button><button onClick={() => api("/api/admin/invites/revoke", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token: i.token }) }).then(loadInvites).catch((e) => setMsg((e as Error).message))} className="border px-2 py-1 rounded">Revoke</button></div>)}</div></section> : null}
    </div>
  );
}
