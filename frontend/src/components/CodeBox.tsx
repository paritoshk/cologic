"use client";

import * as React from "react";

const KW =
  /\b(module|endmodule|input|output|wire|reg|logic|parameter|assign|always|begin|end|case|endcase|default|if|else|posedge|negedge|genvar|generate|for)\b/g;

function hi(line: string) {
  const esc = line
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  if (/^\s*\/\//.test(line)) return `<span class="text-muted-foreground/70">${esc}</span>`;
  let h = esc.replace(KW, '<span class="text-primary">$1</span>');
  h = h.replace(/(\/\/[^<]*)$/, '<span class="text-muted-foreground/70">$1</span>');
  return h;
}

export function CodeBox({
  code,
  filename,
  activeLine,
  activeColor = "var(--primary)",
  height = 320,
}: {
  code: string;
  filename?: string;
  activeLine?: number;
  activeColor?: string;
  height?: number;
}) {
  const lines = code.replace(/\n$/, "").split("\n");
  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      {filename && (
        <div className="flex items-center justify-between px-3 py-2 border-b border-border">
          <span className="font-[family-name:var(--font-jet)] text-xs text-muted-foreground">
            {filename}
          </span>
          <span className="flex gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-border" />
            <span className="w-2.5 h-2.5 rounded-full bg-border" />
            <span className="w-2.5 h-2.5 rounded-full bg-primary/60" />
          </span>
        </div>
      )}
      <div
        className="font-[family-name:var(--font-jet)] text-[11.5px] leading-[1.55] overflow-auto py-2"
        style={{ maxHeight: height }}
      >
        {lines.map((l, i) => {
          const active = activeLine === i;
          return (
            <div
              key={i}
              className="flex px-1"
              style={
                active
                  ? { background: `color-mix(in oklch, ${activeColor} 14%, transparent)` }
                  : undefined
              }
            >
              <span className="w-8 shrink-0 text-right pr-3 select-none text-muted-foreground/50">
                {i + 1}
              </span>
              <span
                className="whitespace-pre text-foreground/90"
                dangerouslySetInnerHTML={{ __html: hi(l) || "&nbsp;" }}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
