import { Navbar } from "@/components/Navbar";
import { Hero } from "@/components/Hero";
import { Optimizer } from "@/components/Optimizer";
import { Benchmark } from "@/components/Benchmark";
import { Forge } from "@/components/Foundry";
import { OptProvider } from "@/lib/opt-context";

export default function Page() {
  return (
    <OptProvider>
      <Navbar />
      <main className="flex-1">
        <div className="snap-start min-h-screen flex flex-col justify-center">
          <Hero />
        </div>
        <div className="border-t border-border" />
        {/* Optimizer + its benchmark read as one view */}
        <div className="snap-start">
          <Optimizer />
          <div className="border-t border-border" />
          <Benchmark />
        </div>
        <div className="border-t border-border" />
        <div className="snap-start min-h-screen flex flex-col justify-center">
          <Forge />
        </div>
      </main>
      <footer className="border-t border-border">
        <div className="mx-auto max-w-6xl px-6 py-8 font-[family-name:var(--font-jet)] text-xs text-muted-foreground">
          Cologic · agents optimize Verilog for fewer gates, equivalence-checked. Benchmark numbers
          are real Verilator eval; optimizer runs live against the grader backend.
        </div>
      </footer>
    </OptProvider>
  );
}
