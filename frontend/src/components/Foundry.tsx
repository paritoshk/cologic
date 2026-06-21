"use client";

import { useEffect, useRef, useState } from "react";
import { fetchFoundry, FOUNDRY_SNAPSHOT, type Foundry as FoundryData } from "@/lib/data";

// Light-themed isometric 8x8 PE lattice with the animated PLAN/FORGE/PROVE minions —
// now driven by live /state data: each agent walks toward the real PE it is working on,
// the roster lists what they're doing, and the epoch ticks. Gate-count + equivalence are
// the signal (see the Optimizer); the lattice is the showcase.

const N = 8;
const TW = 46; // tile width
const TH = 26; // tile height
const OX = 300; // origin x
const OY = 40; // origin y

const ROLE_COLOR: Record<string, { color: string; glow: string }> = {
  PLAN: { color: "#3b82c4", glow: "rgba(59,130,196,0.5)" },
  FORGE: { color: "#3FA34D", glow: "rgba(63,163,77,0.5)" },
  PROVE: { color: "#b8568f", glow: "rgba(184,86,143,0.5)" },
};
const DEFAULT_COLOR = { color: "#7a8a6a", glow: "rgba(122,138,106,0.5)" };
const colorFor = (role: string) => ROLE_COLOR[role] ?? DEFAULT_COLOR;

function iso(i: number, j: number): [number, number] {
  return [OX + (j - i) * (TW / 2), OY + (j + i) * (TH / 2)];
}

// "PE[1][3]" -> [1, 3]; falls back to the origin if no coords are present.
function parseTarget(t: string): [number, number] {
  const m = (t || "").match(/(\d+)\D+(\d+)/);
  return m ? [+m[1], +m[2]] : [0, 0];
}

type Mini = { color: string; glow: string; i: number; j: number; ti: number; tj: number; p: number };

export function Foundry() {
  const [foundry, setFoundry] = useState<FoundryData>(FOUNDRY_SNAPSHOT);
  const [live, setLive] = useState(false);
  const [epoch, setEpoch] = useState(FOUNDRY_SNAPSHOT.epoch);
  const dotsRef = useRef<(SVGGElement | null)[]>([]);
  const pulseRef = useRef<Record<string, SVGPathElement | null>>({});
  const minis = useRef<Mini[]>([]);

  // Seed the walking minions from the live agents' real PE targets. Rebuild only when the
  // agent *count* changes (port of web/index.html's dot-rebuild guard) so positions don't
  // jump on every 8s poll — verb/target/level updates flow through render instead.
  useEffect(() => {
    minis.current = foundry.agents.map((a) => {
      const [i, j] = parseTarget(a.target);
      const c = colorFor(a.role);
      return {
        color: c.color,
        glow: c.glow,
        i,
        j,
        ti: Math.floor(Math.random() * N),
        tj: Math.floor(Math.random() * N),
        p: 0,
      };
    });
    // ponytail: keyed on count only — re-seeding on every 8s poll would make minions jump.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [foundry.agents.length]);

  // Fetch live foundry state on mount, then re-poll every 8s.
  useEffect(() => {
    let alive = true;
    const load = async () => {
      const { data, live: isLive } = await fetchFoundry();
      if (!alive) return;
      setLive(isLive);
      setEpoch(data.epoch);
      setFoundry(data);
    };
    load();
    const poll = setInterval(load, 8000);
    return () => {
      alive = false;
      clearInterval(poll);
    };
  }, []);

  // Epoch ticks slowly while the foundry runs (port of the web/index.html slow tick).
  useEffect(() => {
    const t = setInterval(() => setEpoch((e) => e + 1), 2500);
    return () => clearInterval(t);
  }, []);

  // Animation loop — reads the refs each frame, so it never needs to restart.
  useEffect(() => {
    let raf = 0;
    const speed = 0.018;
    const tick = () => {
      minis.current.forEach((m, k) => {
        m.p += speed;
        if (m.p >= 1) {
          m.p = 0;
          m.i = m.ti;
          m.j = m.tj;
          m.ti = Math.floor(Math.random() * N);
          m.tj = Math.floor(Math.random() * N);
          // light up the destination PE
          const key = `${m.ti}-${m.tj}`;
          const cell = pulseRef.current[key];
          if (cell) {
            cell.style.transition = "none";
            cell.style.fill = "color-mix(in oklch, var(--primary) 30%, var(--card))";
            requestAnimationFrame(() => {
              cell.style.transition = "fill 1.1s ease";
              cell.style.fill = "";
            });
          }
        }
        const ci = m.i + (m.ti - m.i) * m.p;
        const cj = m.j + (m.tj - m.j) * m.p;
        const [x, y] = iso(ci, cj);
        const g = dotsRef.current[k];
        if (g) g.setAttribute("transform", `translate(${x.toFixed(1)},${(y - 7).toFixed(1)})`);
      });
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  const tiles = [];
  for (let i = 0; i < N; i++)
    for (let j = 0; j < N; j++) {
      const [x, y] = iso(i, j);
      tiles.push({ i, j, x, y });
    }

  return (
    <section id="showcase" className="mx-auto max-w-6xl px-6 py-16 scroll-mt-20">
      <div className="font-[family-name:var(--font-jet)] text-[11px] uppercase tracking-[0.14em] text-muted-foreground flex items-center gap-2">
        <span
          className={`w-1.5 h-1.5 rounded-full ${live ? "bg-primary animate-pulse" : "bg-muted-foreground/50"}`}
        />
        {live ? "live foundry" : "foundry · snapshot"}
        <span className="ml-2 normal-case tracking-normal text-muted-foreground/70">
          epoch {epoch.toLocaleString()}
        </span>
      </div>
      <h2 className="font-[family-name:var(--font-instrument)] text-4xl mt-2 mb-2">
        Agents on the array
      </h2>
      <p className="text-foreground/70 max-w-prose mb-8">
        PLAN, FORGE and PROVE walk the 8×8 processing-element array your RTL synthesizes into —
        probing cells, rewriting logic, proving equivalence. Every gate they remove makes the
        silicon smaller.
      </p>

      <div className="rounded-xl border border-border bg-gradient-to-b from-card to-secondary/40 p-6 shadow-sm">
        <svg viewBox="0 0 600 360" className="w-full" style={{ overflow: "visible" }}>
          <defs>
            <filter id="soft" x="-40%" y="-40%" width="180%" height="180%">
              <feDropShadow dx="0" dy="2" stdDeviation="2" floodColor="#000" floodOpacity="0.12" />
            </filter>
          </defs>
          {/* tiles */}
          {tiles.map(({ i, j, x, y }) => {
            const top = `M ${x} ${y - TH / 2} L ${x + TW / 2} ${y} L ${x} ${y + TH / 2} L ${x - TW / 2} ${y} Z`;
            const h = 8;
            const left = `M ${x - TW / 2} ${y} L ${x} ${y + TH / 2} L ${x} ${y + TH / 2 + h} L ${x - TW / 2} ${y + h} Z`;
            const right = `M ${x + TW / 2} ${y} L ${x} ${y + TH / 2} L ${x} ${y + TH / 2 + h} L ${x + TW / 2} ${y + h} Z`;
            return (
              <g key={`${i}-${j}`} filter="url(#soft)">
                <path d={left} fill="color-mix(in oklch, var(--primary) 8%, #d9cfb6)" />
                <path d={right} fill="color-mix(in oklch, var(--primary) 4%, #cfc4a8)" />
                <path
                  ref={(el) => {
                    pulseRef.current[`${i}-${j}`] = el;
                  }}
                  d={top}
                  fill={(i + j) % 2 ? "var(--accent)" : "var(--card)"}
                  stroke="var(--border)"
                  strokeWidth={1}
                  style={{ transition: "fill 1.1s ease" }}
                />
                <circle cx={x} cy={y} r={2} fill="var(--primary)" opacity={0.25} />
              </g>
            );
          })}
          {/* minions — one per live agent */}
          {foundry.agents.map((a, k) => {
            const c = colorFor(a.role);
            return (
              <g
                key={`${a.role}-${k}`}
                ref={(el) => {
                  dotsRef.current[k] = el;
                }}
              >
                <circle r={9} fill={c.glow} opacity={0.6} />
                <circle r={5} fill={c.color} stroke="#fff" strokeWidth={1.5} />
              </g>
            );
          })}
        </svg>

        {/* roster — live role / verb / target / level */}
        <div className="mt-5 grid gap-2 sm:grid-cols-3">
          {foundry.agents.map((a, k) => {
            const c = colorFor(a.role);
            return (
              <div
                key={`${a.role}-${k}`}
                className="flex items-center gap-2 rounded-md border border-border bg-card/60 px-3 py-2"
              >
                <span className="w-2.5 h-2.5 rounded-full flex-none" style={{ background: c.color }} />
                <span
                  className="font-[family-name:var(--font-jet)] text-xs font-semibold"
                  style={{ color: c.color }}
                >
                  {a.role}
                </span>
                <span className="font-[family-name:var(--font-jet)] text-xs text-muted-foreground truncate">
                  {a.verb} {a.target}
                </span>
                <span className="ml-auto font-[family-name:var(--font-jet)] text-[10px] text-muted-foreground/70">
                  LV{a.level}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
