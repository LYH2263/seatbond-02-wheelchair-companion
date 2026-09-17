import { useEffect, useState } from "react";
import { api } from "../api/client";

type Hold = {
  id: number;
  showtime_id: number;
  order_code: string;
  row: number;
  start_col: number;
  end_col: number;
  party_size: number;
  status: string;
  hold_type: string;
  pair_id: number | null;
};

export default function OrdersPage() {
  const [rows, setRows] = useState<Hold[]>([]);
  useEffect(() => {
    api<Hold[]>("/holds").then(setRows);
  }, []);
  return (
    <>
      <h2>订单</h2>
      <table className="table">
        <thead>
          <tr>
            <th>订单号</th>
            <th>场次</th>
            <th>座位</th>
            <th>人数</th>
            <th>类型</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((h) => {
            const isWheel = h.hold_type === "wheelchair";
            return (
              <tr key={h.id}>
                <td className="mono">{h.order_code}</td>
                <td>{h.showtime_id}</td>
                <td className="mono">
                  R{h.row} C{h.start_col}-{h.end_col}
                  {isWheel && (
                    <span style={{ color: "var(--cinema-muted)", fontSize: ".75rem" }}>
                      {" "}（轮椅位+陪同位）
                    </span>
                  )}
                </td>
                <td>{h.party_size}</td>
                <td>
                  {isWheel ? (
                    <span className="tag tag-wheel">轮椅组合 #{h.pair_id}</span>
                  ) : (
                    <span className="tag tag-regular">普通连座</span>
                  )}
                </td>
                <td>{h.status}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </>
  );
}
