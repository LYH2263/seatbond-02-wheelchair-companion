import { useEffect, useState } from "react";
import { api } from "../api/client";

type Pair = {
  id: number;
  wheel_row: number;
  wheel_col: number;
  companion_row: number;
  companion_col: number;
  occupied: boolean;
};
type Hall = {
  id: number;
  name: string;
  rows: number;
  cols: number;
  aisle_cols: number[];
  wheelchair_pairs: Pair[];
};

const emptyForm = { wheel_row: 1, wheel_col: 1, companion_row: 1, companion_col: 2 };

export default function HallsPage() {
  const [rows, setRows] = useState<Hall[]>([]);
  const [hallId, setHallId] = useState<number | "">("");
  const [form, setForm] = useState(emptyForm);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  async function load() {
    const hs = await api<Hall[]>("/halls");
    setRows(hs);
    setHallId((cur) => cur || (hs[0]?.id ?? ""));
  }

  useEffect(() => {
    load();
  }, []);

  const hall = rows.find((h) => h.id === hallId) || null;

  function pickWheel(row: number, col: number) {
    setErr("");
    // companion defaults to an immediate same-row neighbour, preferring the right one
    const companion_col = hall && col < hall.cols && !hall.aisle_cols.includes(col + 1) ? col + 1 : col - 1;
    setForm({ wheel_row: row, wheel_col: col, companion_row: row, companion_col });
  }

  async function submit() {
    setErr("");
    setMsg("");
    if (hallId === "") return;
    try {
      await api(`/halls/${hallId}/wheelchair-pairs`, {
        method: "POST",
        body: JSON.stringify(form),
      });
      setMsg("已登记轮椅位+陪同位组合");
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function remove(pairId: number) {
    setErr("");
    setMsg("");
    if (hallId === "") return;
    try {
      await api(`/halls/${hallId}/wheelchair-pairs/${pairId}`, { method: "DELETE" });
      setMsg("已删除组合");
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <>
      <h2>影厅 · 轮椅位与陪同位</h2>
      <div className="toolbar">
        <label>
          影厅{" "}
          <select value={hallId} onChange={(e) => setHallId(Number(e.target.value))}>
            {rows.map((h) => (
              <option key={h.id} value={h.id}>
                {h.name}（{h.rows}×{h.cols}）
              </option>
            ))}
          </select>
        </label>
        {hall && (
          <span className="mono" style={{ color: "var(--cinema-muted)" }}>
            过道列：{hall.aisle_cols.join(", ") || "—"}
          </span>
        )}
      </div>

      {hall && (
        <>
          <div className="seat-legend">
            <span><span className="chip chip-wheel" />轮椅位</span>
            <span><span className="chip chip-comp" />陪同位（强制邻接、同排、不隔过道）</span>
          </div>

          <div className="toolbar">
            <label>
              轮椅位 行
              <input
                type="number" min={1} max={hall.rows} value={form.wheel_row}
                onChange={(e) => {
                  const r = Number(e.target.value);
                  setForm((f) => ({ ...f, wheel_row: r, companion_row: r }));
                }}
                style={{ width: 64 }}
              />
            </label>
            <label>
              列
              <input
                type="number" min={1} max={hall.cols} value={form.wheel_col}
                onChange={(e) => pickWheel(form.wheel_row, Number(e.target.value))}
                style={{ width: 64 }}
              />
            </label>
            <label>
              陪同位 列
              <input
                type="number" min={1} max={hall.cols} value={form.companion_col}
                onChange={(e) =>
                  setForm((f) => ({ ...f, companion_col: Number(e.target.value) }))
                }
                style={{ width: 64 }}
              />
            </label>
            <button onClick={submit}>登记组合</button>
          </div>
          {msg && <div className="ok">{msg}</div>}
          {err && <div className="err">{err}</div>}

          <table className="table">
            <thead>
              <tr>
                <th>#</th>
                <th>轮椅位</th>
                <th></th>
                <th>陪同位</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {hall.wheelchair_pairs.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ color: "var(--cinema-muted)" }}>
                    该影厅尚未登记轮椅组合
                  </td>
                </tr>
              )}
              {hall.wheelchair_pairs.map((p) => (
                <tr key={p.id}>
                  <td className="mono">{p.id}</td>
                  <td>
                    <span className="tag tag-wheel">
                      轮椅 R{p.wheel_row}C{p.wheel_col}
                    </span>
                  </td>
                  <td className="mono" style={{ color: "var(--cinema-muted)" }}>⇄</td>
                  <td>
                    <span
                      className="tag"
                      style={{
                        background: "rgba(107,74,160,.25)",
                        color: "#c9a8ff",
                        border: "1px solid rgba(200,170,255,.4)",
                      }}
                    >
                      陪同 R{p.companion_row}C{p.companion_col}
                    </span>
                  </td>
                  <td>
                    <button
                      onClick={() => remove(p.id)}
                      style={{ background: "#5a2030", color: "var(--text)" }}
                    >
                      删除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </>
  );
}
