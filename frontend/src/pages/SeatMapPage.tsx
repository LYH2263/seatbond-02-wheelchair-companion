import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";

type Show = { id: number; film_title: string; hall_name?: string };
type Cell = {
  row: number;
  col: number;
  is_aisle: boolean;
  occupied: boolean;
  heat: number;
  seat_kind: "normal" | "wheelchair" | "companion";
  held_kind?: string | null;
  pair_id?: number | null;
};
type MapOut = { showtime_id: number; hall_name: string; rows: number; cols: number; cells: Cell[] };

export default function SeatMapPage() {
  const [shows, setShows] = useState<Show[]>([]);
  const [sid, setSid] = useState<number | "">("");
  const [map, setMap] = useState<MapOut | null>(null);

  useEffect(() => {
    api<Show[]>("/showtimes").then((s) => {
      setShows(s);
      if (s[0]) setSid(s[0].id);
    });
  }, []);

  useEffect(() => {
    if (sid === "") return;
    api<MapOut>(`/seatmap/${sid}`).then(setMap);
  }, [sid]);

  const gridStyle = useMemo(
    () => ({ gridTemplateColumns: map ? `repeat(${map.cols}, 28px)` : undefined }),
    [map]
  );

  return (
    <>
      <div className="toolbar">
        <label>
          场次{" "}
          <select value={sid} onChange={(e) => setSid(Number(e.target.value))}>
            {shows.map((s) => (
              <option key={s.id} value={s.id}>
                {s.film_title} · {s.hall_name}
              </option>
            ))}
          </select>
        </label>
        {map && (
          <span className="mono">
            {map.hall_name} · {map.rows}×{map.cols} · 热力座图
          </span>
        )}
      </div>
      <div className="screen">银 幕</div>
      <div className="seat-legend">
        <span><span className="chip chip-free" />空座</span>
        <span><span className="chip chip-occ" />已占</span>
        <span><span className="chip chip-wheel" />轮椅位</span>
        <span><span className="chip chip-comp" />陪同位</span>
      </div>
      {map && (
        <div className="seat-grid" style={gridStyle}>
          {map.cells.map((c) => {
            const kindClass = c.is_aisle ? "aisle" : c.occupied ? "occ" : "free";
            const seatCls =
              !c.is_aisle && c.seat_kind === "wheelchair" ? "wheel"
              : !c.is_aisle && c.seat_kind === "companion" ? "comp" : "";
            const title =
              c.seat_kind === "wheelchair" ? `轮椅位 R${c.row}C${c.col}`
              : c.seat_kind === "companion" ? `陪同位 R${c.row}C${c.col}`
              : `R${c.row}C${c.col}`;
            return (
              <div
                key={`${c.row}-${c.col}`}
                className={`seat ${kindClass} ${seatCls}`.trim()}
                title={title}
                style={
                  !c.is_aisle && c.heat && c.seat_kind === "normal"
                    ? { boxShadow: `inset 0 0 0 1px rgba(255,180,80,${Math.min(0.9, c.heat / 10)})` }
                    : undefined
                }
              >
                {c.is_aisle ? "" : c.col}
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
