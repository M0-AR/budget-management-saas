import type { ReactNode } from "react";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";

import { cn } from "../lib/utils";
import { Card } from "./ui";

export interface StatDelta {
  text: string;
  direction: "up" | "down" | "flat";
  tone?: "good" | "bad" | "neutral";
}

const DELTA_TONES: Record<"good" | "bad" | "neutral", string> = {
  good: "bg-success-soft text-success",
  bad: "bg-danger-soft text-danger",
  neutral: "bg-surface-2 text-ink-muted",
};

const DELTA_ICONS = {
  up: ArrowUpRight,
  down: ArrowDownRight,
  flat: Minus,
};

export function DeltaChip({ delta }: { delta: StatDelta }) {
  const Icon = DELTA_ICONS[delta.direction];
  const tone =
    delta.tone ?? (delta.direction === "up" ? "good" : delta.direction === "down" ? "bad" : "neutral");
  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[11px] font-semibold",
        DELTA_TONES[tone],
      )}
    >
      <Icon className="size-3" aria-hidden />
      {delta.text}
    </span>
  );
}

export function StatCard({
  label,
  value,
  sub,
  icon,
  delta,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  icon?: ReactNode;
  delta?: StatDelta;
}) {
  return (
    <Card as="div" className="p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-semibold tracking-wide text-ink-muted uppercase">{label}</p>
        {icon ? (
          <span
            className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-surface-2 text-ink-muted"
            aria-hidden
          >
            {icon}
          </span>
        ) : null}
      </div>
      <div className="mt-3 flex flex-wrap items-baseline gap-2">
        <p className="tnum text-2xl font-semibold tracking-tight text-ink">{value}</p>
        {delta ? <DeltaChip delta={delta} /> : null}
      </div>
      {sub ? <div className="mt-1.5 text-xs text-ink-muted">{sub}</div> : null}
    </Card>
  );
}
