// Benchmark numbers — our live Modal data store, fallback to bundled snapshot.

export const STATE_URL = "https://yc-hack27--cologic-web-web.modal.run/state";

export type Task = {
  id: string;
  short: string;
  baseline: number;
  cologic: number;
  bp: string;
  cp: string;
};
export type Benchmark = {
  baseline_model: string;
  cologic_model: string;
  baseline_pass_at_1: number;
  cologic_pass_at_1: number;
  uplift: number;
  gate: number;
  n_per_task: number;
  per_task: Task[];
};

// Bundled snapshot (real eval numbers) so the page renders if the store is down.
export const SNAPSHOT: Benchmark = {
  baseline_model: "Qwen/Qwen3-8B",
  cologic_model: "cologic-rtl",
  baseline_pass_at_1: 0.267,
  cologic_pass_at_1: 0.3,
  uplift: 0.033,
  gate: 0.6,
  n_per_task: 5,
  per_task: [
    { id: "ho_mux2_w16", short: "mux2_w16", baseline: 1.0, cologic: 1.0, bp: "5/5", cp: "5/5" },
    { id: "ho_cmp4", short: "cmp4", baseline: 0.0, cologic: 0.0, bp: "0/5", cp: "0/5" },
    { id: "ho_popcount16", short: "popcount16", baseline: 0.0, cologic: 0.0, bp: "0/5", cp: "0/5" },
    { id: "ho_max2", short: "max2", baseline: 0.4, cologic: 0.6, bp: "2/5", cp: "3/5" },
    { id: "ho_dec2to4", short: "dec2to4", baseline: 0.0, cologic: 0.0, bp: "0/5", cp: "0/5" },
    { id: "ho_gray2bin8", short: "gray2bin8", baseline: 0.2, cologic: 0.2, bp: "1/5", cp: "1/5" },
  ],
};

// Live foundry state — the agents ("minions") editing the Verilog, served from the
// same /state record. We only consume what the showcase renders; power/compute/clock
// synthesis figures are intentionally ignored (gate-count + equivalence are the signal).
// `target` carries the line/region the agent is on; the Forge maps it to a code line.
export type Agent = { role: string; level: number; target: string; verb: string };
export type Foundry = { epoch: number; goal: string; design: string; agents: Agent[] };

// Bundled fallback so the section renders if the store is down.
export const FOUNDRY_SNAPSHOT: Foundry = {
  epoch: 1284,
  goal: "fewer gates",
  design: "mux4.v",
  agents: [
    { role: "PLAN", level: 2, target: "line 8", verb: "reading" },
    { role: "FORGE", level: 3, target: "line 14", verb: "rewriting" },
    { role: "PROVE", level: 4, target: "line 20", verb: "proving" },
  ],
};

export async function fetchFoundry(): Promise<{ data: Foundry; live: boolean }> {
  try {
    const c = new AbortController();
    const to = setTimeout(() => c.abort(), 4000);
    const r = await fetch(STATE_URL, { signal: c.signal, cache: "no-store" });
    clearTimeout(to);
    if (!r.ok) throw new Error("bad status");
    const rec = await r.json();
    const f = rec.foundry;
    if (f && Array.isArray(f.agents)) return { data: f as Foundry, live: true };
    throw new Error("no foundry in record");
  } catch {
    return { data: FOUNDRY_SNAPSHOT, live: false };
  }
}

export async function fetchBenchmark(): Promise<{ data: Benchmark; live: boolean }> {
  try {
    const c = new AbortController();
    const to = setTimeout(() => c.abort(), 4000);
    const r = await fetch(STATE_URL, { signal: c.signal, cache: "no-store" });
    clearTimeout(to);
    if (!r.ok) throw new Error("bad status");
    const rec = await r.json();
    const b = rec.benchmark || rec;
    if (b && typeof b.cologic_pass_at_1 === "number") return { data: b as Benchmark, live: true };
    throw new Error("no benchmark in record");
  } catch {
    return { data: SNAPSHOT, live: false };
  }
}
