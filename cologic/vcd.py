"""Minimal VCD reader for cheap physical proxies.

We don't synthesize, so we approximate from the value-change dump:
  - toggles  = number of signal value changes  -> dynamic-power proxy (lower = better)
  - end_time = last simulation timestamp        -> latency/compute proxy (lower = better)

ponytail: toggle count is unweighted (a 1-bit and a 32-bit change count the same).
Real dynamic power needs per-net capacitance from synthesis; upgrade to yosys + a
liberty library when toggle-count stops correlating with what you care about.
"""


def parse_vcd(path):
    toggles = 0
    end_time = 0
    in_dump = False
    with open(path) as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if not in_dump:
                if line.startswith("$enddefinitions"):
                    in_dump = True
                continue
            c = line[0]
            if c == "#":
                try:
                    end_time = int(line[1:])
                except ValueError:
                    pass
            elif c in "01xzXZbBrR":   # scalar (0/1/x/z) or vector (b.../r...) change
                toggles += 1
    return toggles, end_time


if __name__ == "__main__":
    # self-check: a tiny inline VCD, no iverilog needed
    import tempfile, os, textwrap
    vcd = textwrap.dedent("""\
        $timescale 1ns $end
        $var wire 1 ! clk $end
        $enddefinitions $end
        #0
        0!
        b1010 !
        #10
        1!
        #20
        0!
    """)
    with tempfile.NamedTemporaryFile("w", suffix=".vcd", delete=False) as fh:
        fh.write(vcd)
        p = fh.name
    try:
        toggles, end_time = parse_vcd(p)
        assert toggles == 4, toggles      # 0! b1010 1! 0!
        assert end_time == 20, end_time
        print("vcd self-check OK", toggles, end_time)
    finally:
        os.unlink(p)
