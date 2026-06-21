"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { fetchFoundry, FOUNDRY_SNAPSHOT, type Foundry as FoundryData } from "@/lib/data";
import { useOptOutcome } from "@/lib/opt-context";
import { SAMPLE_RTL, SAMPLE_NAME } from "@/lib/optimizer";

// The Forge: an isometric stack of the Verilog file under optimization. PLAN/FORGE/PROVE
// minions walk the lines and edit them — every FORGE rewrite drops gates, PROVE keeps it
// equivalent. Reflects the real optimizer run (shared via OptContext) when one exists,
// otherwise a snapshot demo. Gate-count + equivalence are the signal; no power/clock here.

const ROLE: Record<string, { color: string; label: string }> = {
  PLAN: { color: "#3b82c4", label: "reads" },
  FORGE: { color: "#3FA34D", label: "rewrites" },
  PROVE: { color: "#b8568f", label: "proves" },
};
const colorOf = (r: string) => ROLE[r]?.color ?? "#7a8a6a";

// isometric stacked-slab geometry
const MAX = 16; // visible lines
const OX = 70;
const OY = 26;
const STEP = 6; // each lower line stairsteps right
const ROW = 30; // vertical pitch
const W = 300; // slab width
const H = 22; // slab face height
const SKEW = 42; // lean
const THK = 8; // slab thickness

const sx = (k: number) => OX + k * STEP;
const sy = (k: number) => OY + k * ROW;

// agent target ("line 14" or backend "PE[1][3]") -> a line index in [0, n)
function targetLine(target: string, n: number): number {
  const nums = (target.match(/\d+/g) || []).map(Number);
  const key = nums.length >= 2 ? nums[0] * 8 + nums[1] : (nums[0] ?? 0);
  return n ? key % n : 0;
}

type Mini = { role: string; color: string; pos: number; from: number; to: number; p: number; speed: number };

function Sprite({ color }: { color: string }) {
  return (
    <>
      <ellipse cx={0} cy={7} rx={9} ry={3.5} fill="#000" opacity={0.12} />
      <rect x={-6} y={-10} width={12} height={15} rx={5} fill="#fff" stroke={color} strokeWidth={2} />
      <circle cx={0} cy={-13} r={5} fill="#fff" stroke={color} strokeWidth={2} />
      <path d={`M -6.5 -15 Q 0 -23 6.5 -15 Z`} fill={color} />
    </>
  );
}

export function Forge() {
  const { outcome } = useOptOutcome();
  const [foundry, setFoundry] = useState<FoundryData>(FOUNDRY_SNAPSHOT);
  const [live, setLive] = useState(false);
  const [epoch, setEpoch] = useState(FOUNDRY_SNAPSHOT.epoch);
  const [edit, setEdit] = useState<{ line: number; drop: number; eq: boolean } | null>(null);

  const dotsRef = useRef<(SVGGElement | null)[]>([]);
  const minis = useRef<Mini[]>([]);
  const editTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const editIdx = useRef(0);

  // The file being forged + its real reward, from the shared optimizer outcome (else demo).
  const code = useMemo(
    () => (outcome?.bestRtl || SAMPLE_RTL).replace(/\n$/, "").split("\n").slice(0, MAX),
    [outcome],
  );
  const n = code.length;
  const file = outcome?.topModule ? `${outcome.topModule}.v` : SAMPLE_NAME;
  const baseline = outcome?.baselineCells ?? 38;
  const best = outcome?.bestCells ?? 31;
  const pct = Math.round((outcome?.areaImprovement ?? (baseline ? (baseline - best) / baseline : 0)) * 100);
  const equiv = outcome?.equivalent ?? true;
  const isDemo = !outcome;

  // per-edit gate drops: real improved steps from history, else a demo cycle
  const deltas = useMemo(() => {
    const h = outcome?.history ?? [];
    const ds: { drop: number; eq: boolean }[] = [];
    for (let i = 1; i < h.length; i++)
      if (h[i].cells < h[i - 1].cells) ds.push({ drop: h[i - 1].cells - h[i].cells, eq: h[i].equivalent });
    return ds.length ? ds : [{ drop: 4, eq: true }, { drop: 3, eq: true }, { drop: 2, eq: true }];
  }, [outcome]);
  // mirror render values into refs so the rAF loop reads the latest without restarting
  const deltasRef = useRef(deltas);
  const nRef = useRef(n);
  useEffect(() => {
    deltasRef.current = deltas;
    nRef.current = n;
  }, [deltas, n]);

  // build minions from live agents; rebuild only on count change
  useEffect(() => {
    minis.current = foundry.agents.map((a, k) => {
      const start = targetLine(a.target, n);
      return {
        role: a.role,
        color: colorOf(a.role),
        pos: start,
        from: start,
        to: (start + 3) % Math.max(1, n),
        p: 0,
        speed: 0.006 + k * 0.0015,
      };
    });
    // ponytail: keyed on count only — re-seeding every poll would make minions jump.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [foundry.agents.length]);

  // fetch live foundry state (agents + epoch), re-poll every 8s
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

  useEffect(() => {
    const t = setInterval(() => setEpoch((e) => e + 1), 2500);
    return () => clearInterval(t);
  }, []);

  // walk loop — minions interpolate between lines; FORGE arriving = an edit
  useEffect(() => {
    let raf = 0;
    const tick = () => {
      minis.current.forEach((m, k) => {
        m.p += m.speed;
        if (m.p >= 1) {
          m.p = 0;
          m.from = m.to;
          m.to = Math.floor(Math.random() * Math.max(1, nRef.current));
          if (m.role === "FORGE") {
            const d = deltasRef.current[editIdx.current % deltasRef.current.length];
            editIdx.current++;
            setEdit({ line: m.from, drop: d.drop, eq: d.eq });
            if (editTimer.current) clearTimeout(editTimer.current);
            editTimer.current = setTimeout(() => setEdit(null), 1500);
          }
        }
        m.pos = m.from + (m.to - m.from) * m.p;
        const g = dotsRef.current[k];
        if (g) g.setAttribute("transform", `translate(${(sx(m.pos) + SKEW + W - 34).toFixed(1)},${(sy(m.pos) + H * 0.5).toFixed(1)})`);
      });
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      if (editTimer.current) clearTimeout(editTimer.current);
    };
  }, []);

  const vw = OX + (MAX - 1) * STEP + SKEW + W + 30;
  const vh = OY + (MAX - 1) * ROW + H + THK + 60;

  return (
    <section id="showcase" className="mx-auto max-w-6xl px-6 py-16 scroll-mt-20">
      <div className="font-[family-name:var(--font-jet)] text-[11px] uppercase tracking-[0.14em] text-muted-foreground flex items-center gap-2">
        <span className={`w-1.5 h-1.5 rounded-full ${live ? "bg-primary animate-pulse" : "bg-muted-foreground/50"}`} />
        {live ? "live forge" : "forge · snapshot"}
        <span className="ml-2 normal-case tracking-normal text-muted-foreground/70">round {epoch.toLocaleString()}</span>
      </div>
      <h2 className="font-[family-name:var(--font-instrument)] text-4xl mt-2 mb-2">Agents editing your Verilog</h2>
      <p className="text-foreground/70 max-w-prose mb-8">
        PLAN reads the module, FORGE rewrites lines for fewer gates, PROVE checks every change stays
        logically equivalent. The stack below is the actual <code className="font-[family-name:var(--font-jet)]">{file}</code>{" "}
        under optimization — each edit drops gates, equivalence-checked.
      </p>

      <div className="rounded-xl border border-border bg-gradient-to-b from-card to-secondary/40 p-5 shadow-sm grid lg:grid-cols-[1fr_248px] gap-5">
        {/* isometric code stack */}
        <svg viewBox={`0 0 ${vw} ${vh}`} className="w-full" style={{ overflow: "visible" }}>
          {code.map((ln, k) => {
            const x = sx(k);
            const y = sy(k);
            const active = edit?.line === k;
            const top = `M ${x + SKEW} ${y} L ${x + SKEW + W} ${y} L ${x + W} ${y + H} L ${x} ${y + H} Z`;
            const front = `M ${x} ${y + H} L ${x + W} ${y + H} L ${x + W} ${y + H + THK} L ${x} ${y + H + THK} Z`;
            return (
              <g key={k}>
                <path d={front} fill="color-mix(in oklch, var(--primary) 10%, #cdc3a8)" />
                <path
                  d={top}
                  fill={active ? "color-mix(in oklch, var(--primary) 26%, var(--card))" : k % 2 ? "var(--accent)" : "var(--card)"}
                  stroke="var(--border)"
                  strokeWidth={1}
                  style={{ transition: "fill .5s ease" }}
                />
                <text
                  x={x + SKEW + 8}
                  y={y + H * 0.68}
                  className="font-[family-name:var(--font-jet)]"
                  fontSize={9}
                  fill="var(--muted-foreground)"
                  opacity={0.55}
                >
                  {k + 1}
                </text>
                <text
                  x={x + SKEW + 30}
                  y={y + H * 0.68}
                  className="font-[family-name:var(--font-jet)]"
                  fontSize={9.5}
                  fill="var(--foreground)"
                  opacity={0.82}
                >
                  {ln.replace(/\t/g, "  ").slice(0, 42) || " "}
                </text>
              </g>
            );
          })}

          {/* live diff / reward chip on the line FORGE just rewrote */}
          {edit && (
            <g transform={`translate(${sx(edit.line) + SKEW + W - 168},${sy(edit.line) - 40})`}>
              <rect x={0} y={0} width={172} height={34} rx={6} fill="var(--card)" stroke="var(--border)" />
              <text x={9} y={14} className="font-[family-name:var(--font-jet)]" fontSize={8.5} fill="#3FA34D" fontWeight={700}>
                FORGE rewrote · line {edit.line + 1}
              </text>
              <text x={9} y={26} className="font-[family-name:var(--font-jet)]" fontSize={8.5} fill="var(--muted-foreground)">
                −{edit.drop} gates{" "}
                <tspan fill={edit.eq ? "#3FA34D" : "#c0504a"}>{edit.eq ? "· equiv ✓" : "· reverted"}</tspan>
              </text>
            </g>
          )}

          {/* minions */}
          {foundry.agents.map((a, k) => (
            <g key={`${a.role}-${k}`} ref={(el) => { dotsRef.current[k] = el; }}>
              <Sprite color={colorOf(a.role)} />
            </g>
          ))}
        </svg>

        {/* side: file tree + verified reward + roster */}
        <div className="flex flex-col gap-4">
          <div className="rounded-lg border border-border bg-card/60 p-3">
            <div className="font-[family-name:var(--font-jet)] text-[9px] uppercase tracking-wide text-muted-foreground mb-2">files</div>
            {[file, `tb_${file.replace(/\.v$/, "")}.v`].map((f, i) => (
              <div
                key={f}
                className={`font-[family-name:var(--font-jet)] text-[11px] py-0.5 flex items-center gap-1.5 ${i === 0 ? "text-foreground" : "text-muted-foreground/70"}`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${i === 0 ? "bg-primary" : "bg-border"}`} />
                {f}
              </div>
            ))}
          </div>

          <div className="rounded-lg border border-primary/40 bg-card p-3">
            <div className="font-[family-name:var(--font-jet)] text-[9px] uppercase tracking-wide text-muted-foreground mb-1.5">
              verified reward {isDemo && <span className="text-muted-foreground/60">· demo</span>}
            </div>
            <div className="flex items-baseline gap-2">
              <span className="font-[family-name:var(--font-jet)] text-2xl font-bold leading-none text-primary">−{pct}%</span>
              <span className="font-[family-name:var(--font-jet)] text-[11px] text-muted-foreground">gates</span>
            </div>
            <div className="font-[family-name:var(--font-jet)] text-[10px] text-muted-foreground mt-1">
              {baseline} → {best} cells
            </div>
            <div className={`mt-2 inline-flex items-center rounded px-2 py-0.5 font-[family-name:var(--font-jet)] text-[10px] ${equiv ? "bg-primary/12 text-primary" : "bg-destructive/12 text-destructive"}`}>
              {equiv ? "equivalence ✓ proven" : "not equivalent ✗"}
            </div>
          </div>

          <div className="rounded-lg border border-border bg-card/60 p-3 flex flex-col gap-1.5">
            <div className="font-[family-name:var(--font-jet)] text-[9px] uppercase tracking-wide text-muted-foreground mb-0.5">agents</div>
            {foundry.agents.map((a, k) => {
              const c = colorOf(a.role);
              return (
                <div key={`${a.role}-${k}`} className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full flex-none" style={{ background: c }} />
                  <span className="font-[family-name:var(--font-jet)] text-[11px] font-semibold" style={{ color: c }}>{a.role}</span>
                  <span className="font-[family-name:var(--font-jet)] text-[10px] text-muted-foreground truncate">
                    {ROLE[a.role]?.label ?? a.verb} · line {targetLine(a.target, n) + 1}
                  </span>
                  <span className="ml-auto font-[family-name:var(--font-jet)] text-[9px] text-muted-foreground/70">LV{a.level}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
