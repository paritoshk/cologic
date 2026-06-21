"use client";

import * as React from "react";

// Light, decorative 8x8 PE grid — "the silicon the RTL maps to". Showcase only.
export function Showcase() {
  const N = 8;
  const cells = [];
  for (let i = 0; i < N; i++)
    for (let j = 0; j < N; j++) cells.push({ i, j });

  return (
    <section id="showcase" className="mx-auto max-w-6xl px-6 py-16 scroll-mt-20">
      <div className="font-[family-name:var(--font-jet)] text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
        showcase
      </div>
      <h2 className="font-[family-name:var(--font-instrument)] text-4xl mt-2 mb-2">
        The silicon your RTL maps to
      </h2>
      <p className="text-foreground/70 max-w-prose mb-8">
        An 8×8 systolic array of processing elements — the structure the optimized Verilog
        synthesizes into. Fewer gates per PE means a smaller, cheaper die. (Illustrative.)
      </p>

      <div className="rounded-xl border border-border bg-card p-8 flex justify-center">
        <svg viewBox="0 0 360 360" className="w-full max-w-md">
          {cells.map(({ i, j }) => (
            <g key={`${i}-${j}`}>
              <rect
                x={20 + j * 42}
                y={20 + i * 42}
                width={34}
                height={34}
                rx={5}
                fill={(i + j) % 2 ? "var(--accent)" : "var(--card)"}
                stroke="var(--border)"
                strokeWidth={1.2}
              />
              <circle
                cx={20 + j * 42 + 17}
                cy={20 + i * 42 + 17}
                r={3}
                fill="var(--primary)"
                opacity={0.35 + ((i * 7 + j) % 5) * 0.13}
              />
            </g>
          ))}
        </svg>
      </div>
    </section>
  );
}
