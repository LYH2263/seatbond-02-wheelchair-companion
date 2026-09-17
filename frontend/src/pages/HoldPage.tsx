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
  hold_type: string;
  pair_id: number | null;
};

export default function HoldPage() {
  const [shows, setShows] = useState<Show[]>([]);
  const [sid, setSid] = useState<number | "">("");
  const [party, setParty] = useState(3);
  const [prefRow, setPrefRow] = useState("");
  const [wheelchair, setWheelchair] = useState(false);
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
        party_size: wheelchair ? 2 : party,
        wheelchair,
      };
      if (prefRow) body.preferred_row = Number(prefRow);
      const hold = await api<Hold>("/holds", { method: "POST", body: JSON.stringify(body) });
      setLast(hold);
      if (hold.hold_type === "wheelchair") {
        setMsg(
          `已锁轮椅组合 ${hold.order_code}：第${hold.row}排 ${hold.start_col}-${hold.end_col}（轮椅位+陪同位，共 ${hold.party_size} 座）`
        );
      } else {
        setMsg(`已锁座 ${hold.order_code}：第${hold.row}排 ${hold.start_col}-${hold.end_col}`);
      }
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
        {!wheelchair && (
          <label>
            人数{" "}
            <input
              type="number"
              min={1}
              max={12}
              value={party}
              onChange={(e) => setParty(Number(e.target.value))}
              style={{ width: 72 }}
            />
          </label>
        )}
        <label>
          优先排{" "}
          <input
            value={prefRow}
            onChange={(e) => setPrefRow(e.target.value)}
            placeholder="可选"
            style={{ width: 72 }}
          />
        </label>
        <label style={{ display: "flex", gap: ".4rem", alignItems: "center" }}>
          <input
            type="checkbox"
            checked={wheelchair}
            onChange={(e) => setWheelchair(e.target.checked)}
            style={{ width: "auto" }}
          />
          轮椅需求（轮椅位+陪同位）
        </label>
        <button onClick={submit}>{wheelchair ? "查找并锁轮椅组合" : "查找并锁连座"}</button>
      </div>
      {wheelchair && (
        <p className="mono" style={{ fontSize: ".75rem", color: "var(--cinema-muted)", marginTop: 0 }}>
          轮椅请求优先占用完整轮椅组合（2 座，含强制邻接陪同位）；陪同位被占时会明确报冲突。
        </p>
      )}
      {msg && <div className="ok">{msg}</div>}
      {err && <div className="err">{err}</div>}
      {last && (
        <p className="mono">
          订单 {last.order_code} · {last.party_size} 人 · R{last.row} C{last.start_col}-{last.end_col}
          {last.hold_type === "wheelchair" && (
            <span className="tag tag-wheel" style={{ marginLeft: 8 }}>轮椅组合 #{last.pair_id}</span>
          )}
        </p>
      )}
    </>
  );
}
