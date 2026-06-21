"""CLI: python -m cologic examples/systolic_array/*.v --top tb"""
import argparse
import json

from .reward import evaluate, _expand


def main():
    ap = argparse.ArgumentParser(prog="cologic", description="verifiable-reward harness")
    ap.add_argument("sources", nargs="+", help=".v files or globs")
    ap.add_argument("--top", default="tb", help="top module to simulate")
    ap.add_argument("--baseline", help="JSON file with {toggles, sim_time} for relative reward")
    ap.add_argument("--w-power", type=float, default=0.5)
    ap.add_argument("--w-compute", type=float, default=0.5)
    a = ap.parse_args()

    baseline = json.load(open(a.baseline)) if a.baseline else None
    res = evaluate(_expand(a.sources), top=a.top, baseline=baseline,
                   w_power=a.w_power, w_compute=a.w_compute)
    print(json.dumps(res.as_dict(), indent=2))


if __name__ == "__main__":
    main()
