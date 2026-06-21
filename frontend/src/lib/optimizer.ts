// Client for Soren's live RTL optimizer backend (Modal). Real gate-count
// reductions: upload Verilog → agents rewrite it → equivalence-checked result.

export const OPT_BASE = "https://yc-hack27--rl-hdl-web.modal.run";
export const DEFAULT_TOKEN = "test123";

// A small default design so the demo runs with zero setup (a 4:1 mux).
export const SAMPLE_NAME = "mux4.v";
export const SAMPLE_RTL = `// mux4.v — 4:1 multiplexer, 8-bit data
module mux4 (
  input  wire [7:0] a,
  input  wire [7:0] b,
  input  wire [7:0] c,
  input  wire [7:0] d,
  input  wire [1:0] sel,
  output reg  [7:0] y
);
  always @(*) begin
    case (sel)
      2'b00: y = a;
      2'b01: y = b;
      2'b10: y = c;
      default: y = d;
    endcase
  end
endmodule
`;

export type Design = {
  id: string;
  reward: number;
  equivalent: boolean;
  ref_cells: number;
  cand_cells: number;
  area_improvement: number;
};
export type Generation = {
  gen: string;
  results?: { mean_reward?: number; designs?: Design[] };
};
export type OptResult = {
  returncode?: number;
  best_gen?: string;
  best_mean_reward?: number;
  best_rtl?: Record<string, string>;
  generations?: Generation[];
};
export type OptOutcome = {
  baselineCells: number;
  bestCells: number;
  areaImprovement: number; // 0..1
  equivalent: boolean;
  bestRtl: string;
  topModule: string;
  generations: Generation[];
};

export type Progress = (msg: string) => void;

function authHeaders(token: string): HeadersInit {
  return { "X-RLHDL-Token": token };
}

export async function runOptimize(opts: {
  rtl: string;
  filename: string;
  prompt: string;
  token?: string;
  mode?: "harness" | "sia";
  onProgress?: Progress;
  signal?: AbortSignal;
}): Promise<OptOutcome> {
  const token = opts.token || DEFAULT_TOKEN;
  const mode = opts.mode || "harness";
  const log = opts.onProgress || (() => {});

  log("uploading design…");
  const fd = new FormData();
  fd.append("files", new File([opts.rtl], opts.filename, { type: "text/plain" }));
  fd.append("prompt", opts.prompt);
  fd.append("mode", mode);
  fd.append("n_candidates", "3");
  fd.append("temperature", "0.7");
  fd.append("max_repair_rounds", "1");
  fd.append("n_vectors", "64");
  if (mode === "harness") fd.append("patience", "2");
  else fd.append("max_generations", "2");

  const sub = await fetch(`${OPT_BASE}/optimize`, {
    method: "POST",
    headers: authHeaders(token),
    body: fd,
    signal: opts.signal,
  });
  if (!sub.ok) throw new Error(`optimize submit failed (${sub.status})`);
  const { job_id, baseline_cells, top_module } = await sub.json();
  log(`parsing ${top_module || "design"} · baseline ${baseline_cells ?? "?"} cells`);

  // poll
  for (let i = 0; i < 90; i++) {
    await new Promise((r) => setTimeout(r, 5000));
    if (opts.signal?.aborted) throw new Error("cancelled");
    const r = await fetch(`${OPT_BASE}/jobs/${job_id}`, {
      headers: authHeaders(token),
      signal: opts.signal,
    });
    if (!r.ok) throw new Error(`poll failed (${r.status})`);
    const j = await r.json();
    if (j.status === "running") {
      log(`optimizing… (${mode}, ${i * 5 + 5}s)`);
      continue;
    }
    if (j.status === "error") throw new Error(j.error || "optimizer error");
    if (j.status === "done") {
      log("done");
      return normalize(j.result as OptResult, baseline_cells, top_module);
    }
  }
  throw new Error("timed out");
}

function normalize(res: OptResult, baselineCells: number, topModule: string): OptOutcome {
  const gens = res.generations || [];
  // best design = highest reward across all generations
  let best: Design | null = null;
  for (const g of gens)
    for (const d of g.results?.designs || [])
      if (!best || d.reward > best.reward) best = d;
  const bestRtl = res.best_rtl ? Object.values(res.best_rtl)[0] || "" : "";
  return {
    baselineCells: best?.ref_cells ?? baselineCells ?? 0,
    bestCells: best?.cand_cells ?? baselineCells ?? 0,
    areaImprovement: best?.area_improvement ?? 0,
    equivalent: best?.equivalent ?? false,
    bestRtl,
    topModule: topModule || (res.best_rtl ? Object.keys(res.best_rtl)[0] : "design"),
    generations: gens,
  };
}
