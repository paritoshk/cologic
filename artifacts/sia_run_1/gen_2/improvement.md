# Generation 2 Improvement Analysis

## Root Cause Analysis of Gen 1 Failure

### Primary Issue: MAX_TOKENS=2048 is fatally small for kimi-k2p7-code

The `kimi-k2p7-code` model is a **chain-of-thought reasoning model**. Before outputting code,
it generates thousands of tokens of step-by-step analysis ("We need to optimize... The four
products are... We can share..."). With `MAX_TOKENS=2048`, the model exhausted its token budget
during the reasoning phase and was cut off before it could produce the `\`\`\`verilog` code
block.

Evidence from the trajectory:
- `rewrite0`: `stage="no_module"`, `reward=0.0` — model output 2000+ tokens of reasoning, no code
- `rewrite1`: `stage="no_module"`, `reward=0.0` — same
- `rewrite2`: `stage="compile_error"`, `reward=0.05` — model just barely produced some code but it
  was malformed (truncated mid-Verilog)
- `rewrite3`: `stage="no_module"`, `reward=0.0` — same as rewrite0/1

The model clearly identified the right optimization (sharing multipliers under output_sel mux),
expressed it in detail in its reasoning, but ran out of tokens before outputting the module.

### Secondary Issue: Repair Loop Skipped no_module

Original repair condition:
```python
while rounds < MAX_REPAIR_ROUNDS and r.info.get("compiled") and not r.info.get("equivalent"):
```

When `stage="no_module"`, `compiled=False`, so the repair loop was **never entered** for the
3 no_module candidates. They were simply abandoned. With `MAX_REPAIR_ROUNDS=1` (env override),
even equivalence failures got at most one repair attempt.

### Environment Overrides

The evaluator set:
- `COLOGIC_N_CANDIDATES=4` (agent default: 6)
- `COLOGIC_MAX_REPAIR=1` (agent default: 2)

These are not bugs — the agent must work well within these constraints.

---

## Improvements Implemented in Generation 2

### Fix 1: MAX_TOKENS = 16384 (was 2048)

This is the critical fix. kimi-k2p7-code needs room for:
- Reasoning/analysis: ~3,000–8,000 tokens
- Verilog code output: ~500–2,000 tokens

16384 provides sufficient headroom without being wasteful. Set via env var
`COLOGIC_MAX_TOKENS` so the evaluator can override if needed.

### Fix 2: Remove `compiled` Guard from Repair Loop

Changed from:
```python
while rounds < MAX_REPAIR_ROUNDS and r.info.get("compiled") and not r.info.get("equivalent"):
```

To:
```python
while rounds < MAX_REPAIR_ROUNDS and not r.info.get("equivalent"):
```

This means **all non-equivalent candidates** (no_module, compile_error, equiv_fail) now receive
repair attempts. Previously, no_module candidates were silently abandoned.

### Fix 3: Specialized no_module Recovery Prompt

When `stage="no_module"`, the model produced no parseable Verilog at all. A standard
"fix your rewrite" repair prompt won't help when there's nothing to fix. Added a dedicated
`SYSTEM_CODE_ONLY` + direct prompt that says:

> "Output ONLY a ```verilog code block. No prose whatsoever."

This forces the model to skip reasoning and immediately output code on the next attempt.

### Fix 4: Extract Module Before Grading

In gen 1, the raw LLM output (reasoning text + maybe code) was passed directly to the grader.
The grader internally calls `extract_module()`, but sending thousands of tokens of reasoning
prose is fragile and wasteful.

Gen 2 applies `extract_module()` BEFORE calling the grader:
```python
cand = extract_module(raw, task.top_module) or raw
```

If a module is found, the grader receives clean Verilog. If not, the raw text is sent (which
will correctly produce `stage="no_module"`).

### Fix 5: Adaptive Hill Climbing

If a candidate beats the baseline, subsequent candidates **refine the best solution** rather
than restarting from the baseline. Uses a dedicated `SYSTEM_REFINE` prompt that tells the
model it already has N cells and should push further.

This is important because gen 2 might find a first improvement quickly, and subsequent rounds
should build on it rather than redundantly applying the same strategy to the baseline.

### Fix 6: Better Strategy Set

Added 6 strategies (vs 5 in gen 1) with more targeted descriptions:
- Strategy 0: Circuit-aware broad sweep (identifies the circuit type and applies the most impactful optimization)
- Strategy 1: Clean rewrite (simple forms that synthesize well)
- Strategy 2: Arithmetic operator sharing (the key optimization for tt_um_tpu)
- Strategy 3: Strength reduction
- Strategy 4: Case/mux simplification
- Strategy 5: Dead code elimination and CSE

Strategy 0 is deliberately broad and instructive — it guides the model to figure out what
kind of optimization matters most for the specific circuit.

### Fix 7: Log Usage Statistics

Each chat call now records `completion_tokens` in the trajectory. This enables post-hoc
analysis of whether MAX_TOKENS is sufficient (if `completion_tokens == MAX_TOKENS`, the
model was still being cut off).

---

## What We Expect in Gen 2

For `tt_um_tpu` specifically, the model correctly identified in gen 1's (truncated) reasoning
that the key optimization is:

- Original: 8 multipliers (a0*b0, a1*b2, a0*b1, a1*b3, a2*b0, a3*b2, a2*b1, a3*b3)
- Optimized: 2 multipliers with muxed inputs based on `output_sel`

```verilog
wire signed [7:0] a_hi = output_sel[1] ? a2 : a0;
wire signed [7:0] a_lo = output_sel[1] ? a3 : a1;
wire signed [7:0] b_hi = output_sel[0] ? b1 : b0;
wire signed [7:0] b_lo = output_sel[0] ? b3 : b2;
wire signed [15:0] c = a_hi * b_hi + a_lo * b_lo;
assign uo_out = output_en ? c[7:0] : 8'd0;
```

This reduces from 8 × (8×8 multiplier) + 4 × (adder) to 2 × (8×8 multiplier) + 1 × (adder)
plus a few 2:1 muxes — a very significant gate count reduction.

With MAX_TOKENS=16384, the model should be able to complete its reasoning and output this code.
