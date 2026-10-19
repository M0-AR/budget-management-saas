import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Info,
  Landmark,
  PiggyBank,
  Target,
  Wallet,
} from "lucide-react";
import { useState } from "react";

import { CategoryBreakdown, TrendChart, UtilizationBar } from "../components/charts";
import { StatCard, type StatDelta } from "../components/StatCard";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  EmptyState,
  PageHeader,
  Skeleton,
  StatusBadge,
} from "../components/ui";
import { api, buildQuery } from "../lib/api";
import { useAuth } from "../lib/auth";
import {
  currentYearMonth,
  formatDate,
  money,
  monthName,
  monthShort,
  percent,
  shiftMonth,
} from "../lib/format";
import type { Dashboard, MonthPoint } from "../lib/types";

function changeDelta(previous: number | undefined, current: number, invert: boolean): StatDelta | null {
  if (previous === undefined || previous <= 0) return null;
  const change = ((current - previous) / previous) * 100;
  if (Math.abs(change) < 0.5) return { text: "0%", direction: "flat", tone: "neutral" };
  const up = change > 0;
  return {
    text: `${up ? "+" : "-"}${Math.abs(change).toFixed(0)}%`,
    direction: up ? "up" : "down",
    tone: up ? (invert ? "bad" : "good") : invert ? "good" : "bad",
  };
}

function monthPoint(trend: MonthPoint[], year: number, month: number): MonthPoint | undefined {
  return trend.find((point) => point.year === year && point.month === month);
}

const VERDICT_STYLES = {
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
  neutral: "text-ink-muted",
} as const;

const VERDICT_ICONS = {
  success: CheckCircle2,
  warning: AlertTriangle,
  danger: AlertTriangle,
  neutral: Info,
} as const;

const ONBOARDING_STEPS = [
  {
    to: "/app/budgets",
    title: "Set this month's budget",
    description: "Pick a monthly spending limit and alert threshold.",
  },
  {
    to: "/app/expenses",
    title: "Log your first expense",
    description: "Record spending to see categories and trends.",
  },
  {
    to: "/app/income",
    title: "Record income",
    description: "Add salary or other income to track savings.",
  },
  {
    to: "/app/settings",
    title: "Invite your team",
    description: "Give teammates the right role in this workspace.",
  },
];

export function DashboardPage() {
  const { tenant, user } = useAuth();
  const currency = tenant?.currency ?? "USD";
  const locale = tenant?.locale ?? "en-US";

  const [{ year, month }, setPeriod] = useState(currentYearMonth);

  const query = useQuery({
    queryKey: ["dashboard", year, month],
    queryFn: () => api.get<Dashboard>(`/api/v1/reports/dashboard${buildQuery({ year, month })}`),
  });

  const data = query.data;
  const isCurrentMonth = (() => {
    const now = currentYearMonth();
    return now.year === year && now.month === month;
  })();

  const now = new Date();
  const daysInMonth = new Date(year, month, 0).getDate();
  const daysLeft = isCurrentMonth ? Math.max(daysInMonth - now.getDate() + 1, 1) : daysInMonth;

  const previousPeriod = shiftMonth(year, month, -1);
  const previousPoint = data ? monthPoint(data.trend, previousPeriod.year, previousPeriod.month) : undefined;
  const spentDelta = data ? changeDelta(previousPoint?.expense, data.expense_total, true) : null;
  const incomeDelta = data ? changeDelta(previousPoint?.income, data.income_total, false) : null;
  const perDay = data && data.remaining > 0 ? data.remaining / Math.max(daysLeft, 1) : 0;
  const isEmpty =
    !!data &&
    data.budget_amount === 0 &&
    data.expense_total === 0 &&
    data.income_total === 0 &&
    data.recent_expenses.length === 0;

  const verdict = (() => {
    if (!data) return { tone: "neutral" as const, text: "" };
    if (data.status === "over") {
      return {
        tone: "danger" as const,
        text: `You're ${money(Math.abs(data.remaining), currency, locale)} over this month's budget.`,
      };
    }
    if (data.status === "warning") {
      return {
        tone: "warning" as const,
        text: `${money(data.remaining, currency, locale)} left — already past ${percent(data.utilization_pct, 0)} of budget.`,
      };
    }
    if (data.status === "no_budget") {
      return { tone: "neutral" as const, text: "No budget set for this month yet — create one to track your pace." };
    }
    return {
      tone: "success" as const,
      text: isCurrentMonth
        ? `${money(data.remaining, currency, locale)} left · ≈ ${money(perDay, currency, locale)}/day for the final ${daysLeft} days.`
        : `${money(data.remaining, currency, locale)} left at month end.`,
    };
  })();
  const VerdictIcon = VERDICT_ICONS[verdict.tone];

  return (
    <>
      <PageHeader
        title={`Good ${now.getHours() < 12 ? "morning" : now.getHours() < 18 ? "afternoon" : "evening"}, ${user?.full_name?.split(" ")[0] || "there"}`}
        subtitle={`${monthName(month)} ${year} · workspace ${tenant?.slug}`}
        actions={
          <div className="flex items-center gap-1.5">
            <Button
              variant="secondary"
              size="sm"
              aria-label="Previous month"
              onClick={() => setPeriod((current) => shiftMonth(current.year, current.month, -1))}
            >
              ←
            </Button>
            {!isCurrentMonth ? (
              <Button variant="ghost" size="sm" onClick={() => setPeriod(currentYearMonth())}>
                Today
              </Button>
            ) : null}
            <Button
              variant="secondary"
              size="sm"
              aria-label="Next month"
              onClick={() => setPeriod((current) => shiftMonth(current.year, current.month, 1))}
            >
              →
            </Button>
          </div>
        }
      />

      {query.isLoading ? (
        <div className="space-y-5" role="status" aria-label="Loading dashboard">
          <Skeleton className="h-56 rounded-xl" />
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {[0, 1, 2, 3].map((key) => (
              <Card key={key} as="div" className="p-5">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="mt-3 h-7 w-32" />
                <Skeleton className="mt-2 h-3 w-20" />
              </Card>
            ))}
          </div>
          <div className="grid gap-5 lg:grid-cols-3">
            <Skeleton className="h-72 rounded-xl lg:col-span-2" />
            <Skeleton className="h-72 rounded-xl" />
          </div>
        </div>
      ) : query.isError || !data ? (
        <Card>
          <div className="p-6 text-sm text-ink-muted">
            Could not load the dashboard.{" "}
            <button className="font-semibold text-accent" onClick={() => void query.refetch()}>
              Retry
            </button>
          </div>
        </Card>
      ) : (
        <div className="space-y-5">
          {isEmpty ? (
            <Card className="p-5 sm:p-6">
              <h2 className="text-base font-semibold tracking-tight">Get your workspace rolling</h2>
              <p className="mt-1 text-sm text-ink-muted">
                Four quick steps and the dashboard comes alive.
              </p>
              <ol className="mt-4 grid gap-2 sm:grid-cols-2">
                {ONBOARDING_STEPS.map((step, index) => (
                  <li key={step.to}>
                    <Link
                      to={step.to}
                      className="flex items-center gap-3 rounded-xl border border-line px-4 py-3 transition hover:bg-surface-2"
                    >
                      <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-surface-2 text-xs font-semibold text-ink-muted">
                        {index + 1}
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-medium">{step.title}</span>
                        <span className="block truncate text-xs text-ink-muted">{step.description}</span>
                      </span>
                      <ArrowRight className="ml-auto size-4 shrink-0 text-ink-muted" aria-hidden />
                    </Link>
                  </li>
                ))}
              </ol>
            </Card>
          ) : null}

          <Card>
            <div className="grid gap-6 p-5 sm:p-6 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)] lg:items-center">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge status={data.status} />
                  <span className="text-xs font-medium text-ink-muted">
                    {monthName(data.month)} {data.year}
                  </span>
                </div>
                <div className="mt-4 flex flex-wrap items-baseline gap-3">
                  <p className="tnum text-4xl font-semibold tracking-tight text-ink sm:text-5xl">
                    {money(data.expense_total, currency, locale)}
                  </p>
                </div>
                <p className="mt-1.5 text-sm text-ink-muted">
                  spent{" "}
                  {data.budget_amount > 0 ? (
                    <>
                      of <span className="font-semibold text-ink">{money(data.budget_amount, currency, locale)}</span>
                    </>
                  ) : (
                    "this month"
                  )}
                  {previousPoint ? ` · vs ${monthShort(previousPeriod.month)} ${String(previousPeriod.year).slice(2)}` : ""}
                </p>
                <p
                  className={`mt-4 flex items-start gap-2 text-sm font-medium ${VERDICT_STYLES[verdict.tone]}`}
                >
                  <VerdictIcon className="mt-0.5 size-4 shrink-0" aria-hidden />
                  {verdict.text}
                </p>
                {data.status === "no_budget" ? (
                  <Link to="/app/budgets" className="mt-3 inline-block">
                    <Button size="sm">Set a budget</Button>
                  </Link>
                ) : null}
              </div>

              <div className="lg:border-l lg:border-line lg:pl-6">
                <div className="flex items-baseline justify-between gap-3">
                  <p className="text-xs font-semibold tracking-wide text-ink-muted uppercase">Utilization</p>
                  <p className="tnum text-xl font-semibold text-ink">
                    {data.budget_amount > 0 ? percent(data.utilization_pct, 1) : "—"}
                  </p>
                </div>
                <div className="mt-3">
                  {data.budget_amount > 0 ? (
                    <UtilizationBar
                      usedPct={data.utilization_pct}
                      thresholdPct={data.alert_threshold_pct}
                    />
                  ) : (
                    <p className="rounded-xl bg-surface-2 px-3.5 py-2.5 text-sm text-ink-muted">
                      Create a budget to track utilization.
                    </p>
                  )}
                </div>
              </div>
            </div>
          </Card>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Monthly budget"
              value={money(data.budget_amount, currency, locale)}
              sub={data.budget_amount > 0 ? `Alert at ${data.alert_threshold_pct}%` : "Not set for this month"}
              icon={<Target className="size-4" />}
            />
            <StatCard
              label="Spent"
              value={money(data.expense_total, currency, locale)}
              icon={<Wallet className="size-4" />}
              delta={spentDelta ?? undefined}
            />
            <StatCard
              label="Remaining"
              value={money(Math.max(data.remaining, 0), currency, locale)}
              icon={<Landmark className="size-4" />}
            />
            <StatCard
              label="Income"
              value={money(data.income_total, currency, locale)}
              sub={`Savings ${money(data.income_total - data.expense_total, currency, locale)}`}
              icon={<PiggyBank className="size-4" />}
              delta={incomeDelta ?? undefined}
            />
          </div>

          <div className="grid gap-5 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader title="Trend" subtitle="Income vs expenses, last 6 months" />
              <div className="px-3 pt-3 pb-4">
                <TrendChart data={data.trend} currency={currency} locale={locale} />
              </div>
            </Card>

            <Card>
              <CardHeader
                title="Spending by category"
                subtitle={`${monthName(data.month)} ${data.year}`}
                action={
                  <Link
                    to="/app/reports"
                    className="text-sm font-semibold text-accent hover:underline"
                  >
                    Full report
                  </Link>
                }
              />
              <div className="px-5 pt-4 pb-5">
                <CategoryBreakdown items={data.by_category} currency={currency} locale={locale} />
              </div>
            </Card>
          </div>

          <Card>
            <CardHeader
              title="Recent expenses"
              subtitle="Latest activity in this workspace"
              action={
                <Link
                  to="/app/expenses"
                  className="inline-flex items-center gap-1 text-sm font-semibold text-accent hover:underline"
                >
                  All expenses <ArrowRight className="size-3.5" />
                </Link>
              }
            />
            <div className="px-5 pt-2 pb-4">
              {data.recent_expenses.length === 0 ? (
                <EmptyState
                  icon={<Wallet className="size-5" />}
                  title="Nothing here yet"
                  description="Record your first expense and it will show up here."
                  action={
                    <Link to="/app/expenses">
                      <Button size="sm">Add expense</Button>
                    </Link>
                  }
                />
              ) : (
                <ul className="divide-y divide-line/70">
                  {data.recent_expenses.map((expense) => (
                    <li key={expense.id} className="flex items-center justify-between gap-3 py-2.5">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">
                          {expense.note || expense.category_name || "Uncategorized"}
                        </p>
                        <p className="truncate text-xs text-ink-muted">
                          {formatDate(expense.happened_on, locale)}
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        {expense.category_color ? (
                          <Badge tone="neutral" className="hidden sm:inline-flex">
                            <span
                              aria-hidden
                              className="size-1.5 rounded-full"
                              style={{ background: expense.category_color }}
                            />
                            {expense.category_name}
                          </Badge>
                        ) : null}
                        <span className="tnum text-sm font-semibold">
                          {money(expense.amount, currency, locale)}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Card>
        </div>
      )}
    </>
  );
}
