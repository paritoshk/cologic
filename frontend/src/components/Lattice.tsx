"use client";

import * as React from "react";
import { useEffect, useRef } from "react";

// Compact animated isometric PE lattice with PLAN/FORGE/PROVE minions.
// Used in the optimizer's right panel while a run is in flight.

const AGENTS = [
  { role: "PLAN", color: "#3b82c4" },
  { role: "FORGE", color: "#3FA34D" },
  { role: "PROVE", color: "#c062a0" },
];

export function Lattice({
  n = 6,
  live = true,
  caption,
}: {
  n?: number;
  live?: boolean;
  caption?: string;
}) {
  const TW = 40,
    TH = 22,
    OX = 200,
    OY = 26;
  const iso = (i: number, j: number): [number, number] => [
    OX + (j - i) * (TW / 2),
    OY + (j + i) * (TH / 2),
  ];
  const dots = useRef<(SVGGElement | null)[]>([]);
  const pulse = useRef<Record<string, SVGPathElement | null>>({});
  const minis = useRef(
    AGENTS.map((a, k) => ({
      ...a,
      i: k * 2,
      j: k,
      ti: (k * 3 + 1) % n,
      tj: (k * 2 + 2) % n,
      p: 0,
    })),
  );

  useEffect(() => {
    let raf = 0;
    const speed = live ? 0.05 : 0.02;
    const tick = () => {
      minis.current.forEach((m, k) => {
        m.p += speed;
        if (m.p >= 1) {
          m.p = 0;
          m.i = m.ti;
          m.j = m.tj;
          m.ti = Math.floor(Math.random() * n);
          m.tj = Math.floor(Math.random() * n);
          const cell = pulse.current[`${m.ti}-${m.tj}`];
          if (cell) {
            cell.style.transition = "none";
            cell.style.fill = `color-mix(in oklch, ${m.color} 35%, var(--card))`;
            requestAnimationFrame(() => {
              cell.style.transition = "fill 1s ease";
              cell.style.fill = "";
            });
          }
        }
        const ci = m.i + (m.ti - m.i) * m.p;
        const cj = m.j + (m.tj - m.j) * m.p;
        const [x, y] = iso(ci, cj);
        const g = dots.current[k];
        if (g) g.setAttribute("transform", `translate(${x.toFixed(1)},${(y - 6).toFixed(1)})`);
      });
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [live, n]);

  const tiles = [];
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) tiles.push({ i, j });

  return (
    <div className="rounded-lg border border-border bg-gradient-to-b from-card to-secondary/40 p-4">
      <svg viewBox="0 0 400 240" className="w-full" style={{ overflow: "visible" }}>
        {tiles.map(({ i, j }) => {
          const [x, y] = iso(i, j);
          const top = `M ${x} ${y - TH / 2} L ${x + TW / 2} ${y} L ${x} ${y + TH / 2} L ${x - TW / 2} ${y} Z`;
          const h = 6;
          const left = `M ${x - TW / 2} ${y} L ${x} ${y + TH / 2} L ${x} ${y + TH / 2 + h} L ${x - TW / 2} ${y + h} Z`;
          const right = `M ${x + TW / 2} ${y} L ${x} ${y + TH / 2} L ${x} ${y + TH / 2 + h} L ${x + TW / 2} ${y + h} Z`;
          return (
            <g key={`${i}-${j}`}>
              <path d={left} fill="color-mix(in oklch, var(--primary) 8%, #d9cfb6)" />
              <path d={right} fill="color-mix(in oklch, var(--primary) 4%, #cfc4a8)" />
              <path
                ref={(el) => {
                  pulse.current[`${i}-${j}`] = el;
                }}
                d={top}
                fill={(i + j) % 2 ? "var(--accent)" : "var(--card)"}
                stroke="var(--border)"
                strokeWidth={0.8}
                style={{ transition: "fill 1s ease" }}
              />
            </g>
          );
        })}
        {minis.current.map((m, k) => (
          <g
            key={m.role}
            ref={(el) => {
              dots.current[k] = el;
            }}
          >
            <circle r={7} fill={m.color} opacity={0.35} />
            <circle r={4} fill={m.color} stroke="#fff" strokeWidth={1.3} />
          </g>
        ))}
      </svg>
      <div className="mt-2 flex items-center justify-between">
        <div className="flex gap-3">
          {AGENTS.map((a) => (
            <span key={a.role} className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full" style={{ background: a.color }} />
              <span className="font-[family-name:var(--font-jet)] text-[10px] text-muted-foreground">
                {a.role}
              </span>
            </span>
          ))}
        </div>
        {caption && (
          <span className="font-[family-name:var(--font-jet)] text-[10px] text-muted-foreground truncate max-w-[55%]">
            {caption}
          </span>
        )}
      </div>
    </div>
  );
}
