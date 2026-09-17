import { useEffect, useState } from "react";
import { api } from "../api/client";

type Show = { id: number; film_title: string; hall_name?: string };
type Hold = {
  id: number;
  order_code: string;
  row: number;
  start_col: number;
  end_col: number;
  party_size: number;
  kind: string;
};

export default function HoldPage() {
  const [shows, setShows] = useState<Show[]>([]);
  const [sid, setSid] = useState<number | "">("");
  const [party, setParty] = useState(3);
  const [prefRow, setPrefRow] = useState("");
  const [wheel, setWheel] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [last, setLast] = useState<Hold | null>(null);

  useEffect(() => {
    api<Show[]>("/showtimes").then((s) => {
      setShows(s);
      if (s[0]) setSid(s[0].id);
    });
  }, []);

  async function submit() {
    setMsg("");
    setErr("");
    try {
      const body: Record<string, unknown> = {
        showtime_id: sid,
        party_size: wheel ? 2 : party,
        wheelchair_need: wheel,
      };
      if (!wheel && prefRow) body.preferred_row = Number(prefRow);
      const hold = await api<Hold>("/holds", { method: "POST", body: JSON.stringify(body) });
      setLast(hold);
      setMsg(
        hold.kind === "wheelchair"
          ? `已锁轮椅组合 ${hold.order_code}：第${hold.row}排 ${hold.start_col}-${hold.end_col}（轮椅位+陪同位）`
          : `已锁座 ${hold.order_code}：第${hold.row}排 ${hold.start_col}-${hold.end_col}`
      );
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <>
      <h2>锁座</h2>
      <div className="toolbar">
        <select value={sid} onChange={(e) => setSid(Number(e.target.value))}>
          {shows.map((s) => (
            <option key={s.id} value={s.id}>
              {s.film_title} · {s.hall_name}
            </option>
          ))}
        </select>
        <label>
          人数{" "}
          <input
            type="number"
            min={1}
            max={12}
            value={wheel ? 2 : party}
            disabled={wheel}
            onChange={(e) => setParty(Number(e.target.value))}
            style={{ width: 72 }}
          />
        </label>
        <label>
          优先排{" "}
          <input
            value={prefRow}
            onChange={(e) => setPrefRow(e.target.value)}
            placeholder="可选"
            disabled={wheel}
            style={{ width: 72 }}
          />
        </label>
        <label className="wheel-toggle">
          <input type="checkbox" checked={wheel} onChange={(e) => setWheel(e.target.checked)} />{" "}
          轮椅需求
        </label>
        <button onClick={submit}>{wheel ? "锁轮椅组合" : "查找并锁连座"}</button>
      </div>
      {wheel && (
        <p className="hint">轮椅需求将锁定完整组合：轮椅位 + 同排相邻陪同位，人数按组合座位数计为 2。</p>
      )}
      {msg && <div className="ok">{msg}</div>}
      {err && <div className="err">{err}</div>}
      {last && (
        <p className="mono">
          订单 {last.order_code} · {last.party_size} 人 · R{last.row} C{last.start_col}-{last.end_col}
          {last.kind === "wheelchair" && " · ♿ 轮椅组合"}
        </p>
      )}
    </>
  );
}
