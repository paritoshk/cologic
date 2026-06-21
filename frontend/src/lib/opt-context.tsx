"use client";

// Shares the latest optimizer result between the Optimizer panel (producer) and the
// Forge showcase (consumer) so the isometric scene reflects the real run.
import { createContext, useContext, useState } from "react";
import type { OptOutcome } from "@/lib/optimizer";

type Ctx = { outcome: OptOutcome | null; setOutcome: (o: OptOutcome | null) => void };
const OptContext = createContext<Ctx | null>(null);

export function OptProvider({ children }: { children: React.ReactNode }) {
  const [outcome, setOutcome] = useState<OptOutcome | null>(null);
  return <OptContext.Provider value={{ outcome, setOutcome }}>{children}</OptContext.Provider>;
}

export function useOptOutcome(): Ctx {
  const c = useContext(OptContext);
  if (!c) throw new Error("useOptOutcome must be used within OptProvider");
  return c;
}
