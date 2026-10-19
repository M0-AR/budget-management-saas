import { useId } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { money, monthShort, percent } from "../lib/format";
import type { CategoryTotal, MonthPoint } from "../lib/types";
import { cn } from "../lib/utils";

interface TooltipEntry {
  name: string;
  value: number;
  color: string;
}

const NAME_LABELS: Record<string, string> = {
  income: "Income",
  expense: "Expense",
};

function ChartTooltip({
  label,
  entries,
  currency,
  locale,
}: {
  label?: string;
  entries: TooltipEntry[];
  currency: string;
  locale: string;
}) {
  return (
    <div className="min-w-36 rounded-xl border border-line bg-surface-1 px-3 py-2.5 shadow-lg">
      {label ? (
        <p className="text-[11px] font-semibold tracking-wide text-ink-muted uppercase">{label}</p>
      ) : null}
      <ul className="mt-1.5 space-y-1">
        {entries.map((entry) => (
          <li key={entry.name} className="flex items-center justify-between gap-4 text-xs">
            <span className="flex items-center gap-1.5 text-ink-muted">
              <span aria-hidden className="size-2 rounded-full" style={{ background: entry.color }} />
              {entry.name}
            </span>
            <span className="tnum font-semibold text-ink">{money(entry.value, currency, locale)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function TrendChart({
  data,
  currency,
  locale,
}: {
  data: MonthPoint[];
  currency: string;
  locale: string;
}) {
  const points = data.map((point) => ({
    ...point,
    label: `${monthShort(point.month)} ${String(point.year).slice(2)}`,
  }));

  const totalIncome = data.reduce((sum, point) => sum + point.income, 0);
  const totalExpense = data.reduce((sum, point) => sum + point.expense, 0);

  return (
    <div
      role="img"
      aria-label={`Six-month trend. Income ${money(totalIncome, currency, locale)} total, expenses ${money(totalExpense, currency, locale)} total.`}
      className="h-64 w-full"
    >
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={points} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="gradientIncome" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--success)" stopOpacity={0.2} />
              <stop offset="100%" stopColor="var(--success)" stopOpacity={0.02} />
            </linearGradient>
            <linearGradient id="gradientExpense" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.2} />
              <stop offset="100%" stopColor="var(--accent)" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="var(--line)" strokeOpacity={0.7} strokeDasharray="3 6" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fill: "var(--ink-muted)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            tickMargin={8}
          />
          <YAxis
            tick={{ fill: "var(--ink-muted)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            tickMargin={6}
            width={52}
            tickFormatter={(value: number) =>
              new Intl.NumberFormat(locale, { notation: "compact" }).format(value)
            }
          />
          <Tooltip
            cursor={{ stroke: "var(--line)", strokeWidth: 1 }}
            content={(props) => {
              if (!props.active || !props.payload?.length) return null;
              const entries: TooltipEntry[] = props.payload.map((entry) => ({
                name: NAME_LABELS[String(entry.name ?? "")] ?? String(entry.name ?? ""),
                value: typeof entry.value === "number" ? entry.value : Number(entry.value ?? 0),
                color: entry.color ?? "var(--accent)",
              }));
              return (
                <ChartTooltip
                  label={typeof props.label === "string" ? props.label : undefined}
                  entries={entries}
                  currency={currency}
                  locale={locale}
                />
              );
            }}
          />
          <Legend
            iconType="circle"
            iconSize={8}
            formatter={(value: string) => (
              <span style={{ color: "var(--ink-muted)", fontSize: 12 }}>
                {NAME_LABELS[value] ?? value}
              </span>
            )}
          />
          <Area
            type="monotone"
            dataKey="income"
            name="income"
            stroke="var(--success)"
            strokeWidth={2}
            fill="url(#gradientIncome)"
            dot={false}
            activeDot={{ r: 3.5, strokeWidth: 2, stroke: "var(--surface-1)" }}
            animationDuration={500}
          />
          <Area
            type="monotone"
            dataKey="expense"
            name="expense"
            stroke="var(--accent)"
            strokeWidth={2}
            fill="url(#gradientExpense)"
            dot={false}
            activeDot={{ r: 3.5, strokeWidth: 2, stroke: "var(--surface-1)" }}
            animationDuration={500}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function Sparkline({
  values,
  label,
  tone = "accent",
  className,
}: {
  values: number[];
  label: string;
  tone?: "accent" | "success" | "danger";
  className?: string;
}) {
  const gradientId = useId().replace(/:/g, "");

  if (values.length < 2) return null;

  const width = 120;
  const height = 36;
  const pad = 3;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;

  const points = values.map((value, index) => ({
    x: (index / (values.length - 1)) * width,
    y: height - pad - ((value - min) / span) * (height - pad * 2),
  }));

  const line = points
    .map((point, index) => `${index === 0 ? "M" : "L"}${point.x.toFixed(1)} ${point.y.toFixed(1)}`)
    .join(" ");
  const area = `${line} L${width} ${height} L0 ${height} Z`;
  const stroke =
    tone === "success" ? "var(--success)" : tone === "danger" ? "var(--danger)" : "var(--accent)";

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      role="img"
      aria-label={label}
      className={cn("h-9 w-full", className)}
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity={0.2} />
          <stop offset="100%" stopColor={stroke} stopOpacity={0.02} />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gradientId})`} />
      <path
        d={line}
        fill="none"
        stroke={stroke}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

export function CategoryBreakdown({
  items,
  currency,
  locale,
  className,
}: {
  items: CategoryTotal[];
  currency: string;
  locale: string;
  className?: string;
}) {
  if (items.length === 0) {
    return <p className="px-5 py-8 text-center text-sm text-ink-muted">No spending recorded yet.</p>;
  }

  const top = Math.max(...items.map((item) => item.share_pct), 1);

  return (
    <ul className={cn("space-y-4", className)}>
      {items.map((item) => (
        <li key={item.category_id ?? item.name}>
          <div className="flex items-baseline justify-between gap-3">
            <span className="flex min-w-0 items-center gap-2 text-sm font-medium text-ink">
              <span
                aria-hidden
                className="size-2 shrink-0 rounded-full"
                style={{ background: item.color }}
              />
              <span className="truncate">{item.name}</span>
            </span>
            <span className="tnum shrink-0 text-sm text-ink-muted">
              {money(item.amount, currency, locale)}
              <span className="ml-2 text-xs">({percent(item.share_pct, 1)})</span>
            </span>
          </div>
          <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface-2">
            <div
              role="presentation"
              className="h-full w-full origin-left rounded-full transition-transform duration-500"
              style={{
                transform: `scaleX(${Math.max(item.share_pct / top, 0.02)})`,
                background: item.color,
              }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}

export function UtilizationBar({
  usedPct,
  thresholdPct,
}: {
  usedPct: number;
  thresholdPct: number;
}) {
  const clamped = Math.min(Math.max(usedPct, 0), 100);
  const over = usedPct > 100;
  const near = !over && usedPct >= thresholdPct;
  const fill = over ? "bg-danger" : near ? "bg-warning" : "bg-accent";

  return (
    <div>
      <div className="relative h-2.5 overflow-hidden rounded-full bg-surface-2">
        <div
          role="progressbar"
          aria-valuenow={Math.round(clamped)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Budget utilization"
          className={cn("h-full w-full origin-left rounded-full transition-transform duration-500", fill)}
          style={{ transform: `scaleX(${clamped / 100})` }}
        />
        <div
          aria-hidden
          title={`Alert threshold ${thresholdPct}%`}
          className="absolute inset-y-0 w-0.5 -translate-x-1/2 bg-ink-muted/70"
          style={{ left: `${Math.min(thresholdPct, 100)}%` }}
        />
      </div>
      <div className="mt-1 flex justify-between text-xs text-ink-muted">
        <span>{percent(usedPct, 1)} used</span>
        <span>alert at {thresholdPct}%</span>
      </div>
    </div>
  );
}
