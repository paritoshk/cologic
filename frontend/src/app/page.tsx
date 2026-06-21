import { Navbar } from "@/components/Navbar";
import { Hero } from "@/components/Hero";
import { Optimizer } from "@/components/Optimizer";
import { Benchmark } from "@/components/Benchmark";
import { Showcase } from "@/components/Showcase";

export default function Page() {
  return (
    <>
      <Navbar />
      <main className="flex-1">
        <Hero />
        <div className="border-t border-border" />
        <Optimizer />
        <div className="border-t border-border" />
        <Benchmark />
        <div className="border-t border-border" />
        <Showcase />
      </main>
      <footer className="border-t border-border">
        <div className="mx-auto max-w-6xl px-6 py-8 font-[family-name:var(--font-jet)] text-xs text-muted-foreground">
          Cologic · agents optimize Verilog for fewer gates, equivalence-checked. Benchmark numbers
          are real Verilator eval; optimizer runs live against the grader backend.
        </div>
      </footer>
    </>
  );
}
