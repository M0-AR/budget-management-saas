import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Download, PieChart } from "lucide-react";

import { CategoryBreakdown, UtilizationBar } from "../components/charts";
import { StatCard } from "../components/StatCard";
import {
  Button,
  Card,
  CardHeader,
  EmptyState,
  LoadingPanel,
  PageHeader,
  Select,
  StatusBadge,
  useToast,
} from "../components/ui";
import { api, buildQuery, downloadFile } from "../lib/api";
import { useAuth } from "../lib/auth";
import { currentYearMonth, money, monthName } from "../lib/format";
import type { MonthlyReport } from "../lib/types";

const YEAR_SPAN = 3;

export function ReportsPage() {
  const { tenant } = useAuth();
  const { push } = useToast();

  const currency = tenant?.currency ?? "USD";
  const locale = tenant?.locale ?? "en-US";
  const now = currentYearMonth();

  const [year, setYear] = useState(now.year);
  const [month, setMonth] = useState(now.month);

  const query = useQuery({
    queryKey: ["reports", "monthly", year, month],
    queryFn: () => api.get<MonthlyReport>(`/api/v1/reports/monthly${buildQuery({ year, month })}`),
  });

  const data = query.data;
  const saving = data ? data.income_total - data.expense_total : 0;

  const onExport = async () => {
    try {
      await downloadFile(
        `/api/v1/exports/transactions.csv${buildQuery({ year, month })}`,
        `transactions-${year}-${String(month).padStart(2, "0")}.csv`,
      );
      push({ tone: "info", title: "Export ready", description: "The CSV was downloaded." });
    } catch {
      push({ tone: "danger", title: "Export failed", description: "Please try again." });
    }
  };

  return (
    <>
      <PageHeader
        title="Reports"
        subtitle="Monthly performance, category by category."
        actions={
          <>
            <Select
              aria-label="Report month"
              value={month}
              onChange={(event) => setMonth(Number(event.target.value))}
              className="w-36"
            >
              {Array.from({ length: 12 }, (_, index) => index + 1).map((option) => (
                <option key={option} value={option}>
                  {monthName(option)}
                </option>
              ))}
            </Select>
            <Select
              aria-label="Report year"
              value={year}
              onChange={(event) => setYear(Number(event.target.value))}
              className="w-28"
            >
              {Array.from({ length: YEAR_SPAN * 2 + 1 }, (_, index) => now.year - YEAR_SPAN + index).map(
                (option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ),
              )}
            </Select>
            <Button variant="secondary" icon={<Download className="size-4" />} onClick={onExport}>
              Export CSV
            </Button>
          </>
        }
      />

      {query.isLoading ? (
        <Card>
          <LoadingPanel label="Loading report" />
        </Card>
      ) : query.isError || !data ? (
        <Card>
          <EmptyState
            icon={<PieChart className="size-5" />}
            title="Could not load this report"
            action={
              <Button variant="secondary" onClick={() => void query.refetch()}>
                Retry
              </Button>
            }
          />
        </Card>
      ) : (
        <div className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Income"
              value={money(data.income_total, currency, locale)}
              icon={<span aria-hidden>↑</span>}
            />
            <StatCard
              label="Expenses"
              value={money(data.expense_total, currency, locale)}
              icon={<span aria-hidden>↓</span>}
            />
            <StatCard
              label="Savings"
              value={money(saving, currency, locale)}
              sub={data.income_total > 0 ? `${((saving / data.income_total) * 100).toFixed(1)}% of income` : undefined}
              icon={<span aria-hidden>◆</span>}
            />
            <StatCard
              label="Budget used"
              value={data.budget_amount > 0 ? `${data.utilization_pct.toFixed(1)}%` : "—"}
              sub={
                data.budget_amount > 0
                  ? `${money(data.expense_total, currency, locale)} of ${money(data.budget_amount, currency, locale)}`
                  : "No budget for this month"
              }
              icon={<span aria-hidden>◎</span>}
            />
          </div>

          <div className="grid gap-5 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader
                title="Category breakdown"
                subtitle={`${monthName(data.month)} ${data.year}`}
                action={
                  <span className="tnum text-sm font-semibold text-ink">
                    {money(data.expense_total, currency, locale)}
                  </span>
                }
              />
              <div className="px-5 pt-4 pb-5">
                <CategoryBreakdown items={data.by_category} currency={currency} locale={locale} />
              </div>
            </Card>

            <Card>
              <CardHeader
                title="Budget performance"
                subtitle={`${monthName(data.month)} ${data.year}`}
                action={<StatusBadge status={data.status} />}
              />
              <div className="space-y-5 px-5 pt-4 pb-5">
                <UtilizationBar usedPct={data.utilization_pct} thresholdPct={data.alert_threshold_pct} />
                <dl className="space-y-3 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-ink-muted">Budget</dt>
                    <dd className="tnum font-medium">{money(data.budget_amount, currency, locale)}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-ink-muted">Spent</dt>
                    <dd className="tnum font-medium">{money(data.expense_total, currency, locale)}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-ink-muted">Remaining</dt>
                    <dd
                      className={
                        data.remaining < 0
                          ? "tnum font-semibold text-danger"
                          : "tnum font-semibold text-success"
                      }
                    >
                      {money(data.remaining, currency, locale)}
                    </dd>
                  </div>
                  <div className="flex justify-between border-t border-line pt-3">
                    <dt className="text-ink-muted">Net savings</dt>
                    <dd
                      className={
                        saving < 0 ? "tnum font-semibold text-danger" : "tnum font-semibold text-success"
                      }
                    >
                      {money(saving, currency, locale)}
                    </dd>
                  </div>
                </dl>
              </div>
            </Card>
          </div>
        </div>
      )}
    </>
  );
}
