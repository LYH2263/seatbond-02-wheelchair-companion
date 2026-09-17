import { useEffect, useState } from "react";
import { api } from "../api/client";

type Pair = { id: number; hall_id: number; row: number; col: number; companion_col: number };
type Hall = {
  id: number;
  name: string;
  rows: number;
  cols: number;
  aisle_cols: number[];
  wheelchair_pairs: Pair[];
};

export default function HallsPage() {
  const [rows, setRows] = useState<Hall[]>([]);
  const [hid, setHid] = useState<number | "">("");
  const [row, setRow] = useState("");
  const [col, setCol] = useState("");
  const [companion, setCompanion] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  function refresh() {
    api<Hall[]>("/halls").then(setRows);
  }
  useEffect(() => {
    refresh();
  }, []);

  const hall = rows.find((h) => h.id === hid) ?? rows[0];
  const pairs = hall ? [...hall.wheelchair_pairs].sort((a, b) => a.row - b.row || a.col - b.col) : [];

  async function addPair() {
    if (!hall) return;
    setMsg("");
    setErr("");
    try {
      await api<Pair>(`/halls/${hall.id}/wheelchair-pairs`, {
        method: "POST",
        body: JSON.stringify({ row: Number(row), col: Number(col), companion_col: Number(companion) }),
      });
      setMsg(`已登记：第${row}排 轮椅位${col}列 + 陪同位${companion}列`);
      setRow("");
      setCol("");
      setCompanion("");
      refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function removePair(p: Pair) {
    setMsg("");
    setErr("");
    try {
      await api(`/halls/${p.hall_id}/wheelchair-pairs/${p.id}`, { method: "DELETE" });
      setMsg(`已删除：第${p.row}排 轮椅位${p.col}列 + 陪同位${p.companion_col}列`);
      refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <>
      <h2>影厅</h2>
      <table className="table">
        <thead>
          <tr>
            <th>名称</th>
            <th>行×列</th>
            <th>过道列</th>
            <th>轮椅位 / 陪同位</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((h) => (
            <tr key={h.id}>
              <td>{h.name}</td>
              <td className="mono">
                {h.rows} × {h.cols}
              </td>
              <td className="mono">{h.aisle_cols.join(", ") || "—"}</td>
              <td className="mono">
                {h.wheelchair_pairs.length === 0 && "—"}
                {h.wheelchair_pairs.map((p) => (
                  <span key={p.id} className="pair-tag">
                    R{p.row} ♿{p.col} + 伴{p.companion_col}
                  </span>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2 style={{ marginTop: "1.5rem" }}>轮椅位登记</h2>
      <p className="hint">轮椅位必须绑定同排左右相邻的陪同位（不得隔过道）；陪同位受保护，普通连座不可单独占用。</p>
      <div className="toolbar">
        <label>
          影厅{" "}
          <select value={hall?.id ?? ""} onChange={(e) => setHid(Number(e.target.value))}>
            {rows.map((h) => (
              <option key={h.id} value={h.id}>
                {h.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          排 <input value={row} onChange={(e) => setRow(e.target.value)} style={{ width: 56 }} />
        </label>
        <label>
          轮椅位列 <input value={col} onChange={(e) => setCol(e.target.value)} style={{ width: 56 }} />
        </label>
        <label>
          陪同位列{" "}
          <input value={companion} onChange={(e) => setCompanion(e.target.value)} style={{ width: 56 }} />
        </label>
        <button onClick={addPair} disabled={!hall || !row || !col || !companion}>
          登记组合
        </button>
      </div>
      {msg && <div className="ok">{msg}</div>}
      {err && <div className="err">{err}</div>}
      {hall && (
        <table className="table">
          <thead>
            <tr>
              <th>排</th>
              <th>轮椅位列</th>
              <th>陪同位列</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {pairs.length === 0 && (
              <tr>
                <td colSpan={4} className="mono">
                  {hall.name} 尚未登记轮椅位
                </td>
              </tr>
            )}
            {pairs.map((p) => (
              <tr key={p.id}>
                <td className="mono">R{p.row}</td>
                <td className="mono">♿ {p.col}</td>
                <td className="mono">伴 {p.companion_col}</td>
                <td>
                  <button className="btn-ghost" onClick={() => removePair(p)}>
                    删除
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
