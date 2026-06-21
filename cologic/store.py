"""The site's data store — the record schema + a Modal-Dict-backed publish/seed.

The website fetches one JSON record (benchmark + foundry state) from a live Modal
endpoint (see serve.py). This module builds that record and writes it to the
Modal Dict the endpoint reads. `web/data.json` is also written as an offline
fallback so the static site never breaks if the endpoint is down.

  python -m cologic.store --seed            # build record from web/data.json + publish
  python -m cologic.store --selfcheck
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

DICT_NAME = "cologic-state"
KEY = "latest"
WEB_JSON = Path("web/data.json")

# Foundry panel defaults (the live demo design). Benchmark numbers are real eval
# output; these synthesis figures are seed values served live — wire to real
# yosys/OpenSTA later by overwriting them in publish().
FOUNDRY_DEFAULT = {
    "design": "tensor-mac / systolic_8×8",
    "objective": "power",
    "pdk": "sky130hd",
    "epoch": 1284,
    "power_rel": 142,
    "compute_pct": 71,
    "clock_mhz": 910,
    "sim_status": "PASS",
    "demo": True,  # synthesis figures are illustrative until wired to real synth
    "agents": [
        {"role": "PLAN", "level": 2, "target": "PE[1][3]", "verb": "probing"},
        {"role": "FORGE", "level": 3, "target": "PE[2][2]", "verb": "sampling"},
        {"role": "PROVE", "level": 4, "target": "PE[5][5]", "verb": "sampling"},
    ],
    "rtl": (
        "// systolic_array.v — 8x8 output-stationary INT8\n"
        "// FORGE · objective: power · pdk: sky130hd\n"
        "`timescale 1ns/1ps\n"
        "`default_nettype none\n"
        "\n"
        "module systolic_array #(\n"
        "  parameter int N  = 8,        // array dim\n"
        "  parameter int IW = 8,        // operand width\n"
        "  parameter int OW = 2*IW + 4  // 20-bit accumulator\n"
        ")(\n"
        "  input  wire                  clk,\n"
        "  input  wire                  rst_n,\n"
        "  input  wire                  in_valid,\n"
        "  input  wire signed [IW-1:0]  a_row [N],\n"
        "  input  wire signed [IW-1:0]  b_col [N],\n"
        "  output reg                   out_valid,\n"
        "  output reg  signed [OW-1:0]  c_mac [N][N]\n"
        ");\n"
        "  // A flows west->east, B flows north->south\n"
        "  logic signed [IW-1:0] a_h [N][N+1];\n"
        "  logic signed [IW-1:0] b_v [N+1][N];\n"
        "\n"
        "  genvar i, j;\n"
        "  generate\n"
        "    for (i = 0; i < N; i++) begin : g_row\n"
        "      for (j = 0; j < N; j++) begin : g_col\n"
        "        pe #(.IW(IW), .OW(OW)) u_pe (\n"
        "          .clk (clk), .rst_n (rst_n), .en (in_valid),\n"
        "          .a_in (a_h[i][j]),  .a_out (a_h[i][j+1]),\n"
        "          .b_in (b_v[i][j]),  .b_out (b_v[i+1][j]),\n"
        "          .c_acc(c_mac[i][j]) );\n"
        "      end\n"
        "    end\n"
        "  endgenerate\n"
        "endmodule\n"
    ),
}


def build_record(benchmark: dict, foundry: dict | None = None, *, updated_at: str = "") -> dict:
    """Assemble the full site record from a benchmark dict + foundry panel."""
    return {
        "updated_at": updated_at,
        "source": benchmark.get("source", "unknown"),
        "benchmark": benchmark,
        "foundry": {**FOUNDRY_DEFAULT, **(foundry or {})},
    }


def publish(record: dict) -> None:
    """Write the record to the Modal Dict the live endpoint serves."""
    import modal

    d = modal.Dict.from_name(DICT_NAME, create_if_missing=True)
    d[KEY] = record
    print(f"published to modal Dict {DICT_NAME!r}[{KEY!r}] (source={record.get('source')})")


def seed_from_web_json(path: Path = WEB_JSON, *, updated_at: str = "") -> dict:
    """Build the record from the committed web/data.json benchmark numbers."""
    benchmark = json.loads(path.read_text())
    return build_record(benchmark, updated_at=updated_at)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true", help="build record from web/data.json and publish")
    ap.add_argument("--updated-at", default="", help="ISO timestamp to stamp the record")
    ap.add_argument("--selfcheck", action="store_true")
    args = ap.parse_args()

    if args.selfcheck:
        _selfcheck()
        return
    if args.seed:
        rec = seed_from_web_json(updated_at=args.updated_at)
        publish(rec)
        return
    ap.print_help()


def _selfcheck() -> None:
    bm = {"source": "test", "baseline_pass_at_1": 0.267, "cologic_pass_at_1": 0.3, "per_task": []}
    rec = build_record(bm, {"power_rel": 99})
    assert rec["benchmark"]["baseline_pass_at_1"] == 0.267
    assert rec["foundry"]["power_rel"] == 99  # override applied
    assert rec["foundry"]["compute_pct"] == 71  # default kept
    assert rec["foundry"]["rtl"].startswith("// systolic_array.v")
    assert rec["source"] == "test"
    print("store selfcheck OK")


if __name__ == "__main__":
    main()
