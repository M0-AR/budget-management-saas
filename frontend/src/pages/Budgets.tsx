import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { CalendarRange, Pencil, Plus, Trash2 } from "lucide-react";

import {
  Button,
  Card,
  CardHeader,
  Dialog,
  EmptyState,
  Field,
  Input,
  LoadingPanel,
  PageHeader,
  Select,
  StatusBadge,
  useToast,
} from "../components/ui";
import { api, ApiRequestError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { currentYearMonth, money, monthName, percent } from "../lib/format";
import type { Budget, Dashboard } from "../lib/types";

interface BudgetForm {
  month: number;
  amount: string;
  alert_threshold_pct: string;
}

const YEAR_SPAN = 3;

export function BudgetsPage() {
  const { tenant, user } = useAuth();
  const queryClient = useQueryClient();
  const { push } = useToast();

  const currency = tenant?.currency ?? "USD";
  const locale = tenant?.locale ?? "en-US";
  const canWrite = user?.role !== "viewer";

  const now = currentYearMonth();
  const [year, setYear] = useState(now.year);
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<BudgetForm>({
    month: now.month,
    amount: "",
    alert_threshold_pct: "80",
  });
  const [formError, setFormError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<Budget | null>(null);

  const budgetsQuery = useQuery({
    queryKey: ["budgets", year],
    queryFn: () => api.get<Budget[]>(`/api/v1/budgets?year=${year}`),
  });

  const dashboardQuery = useQuery({
    queryKey: ["dashboard", now.year, now.month],
    queryFn: () =>
      api.get<Dashboard>(`/api/v1/reports/dashboard?year=${now.year}&month=${now.month}`),
  });

  const invalidateBudgetViews = () => {
    void queryClient.invalidateQueries({ queryKey: ["budgets"] });
    void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    void queryClient.invalidateQueries({ queryKey: ["reports"] });
  };

  const restoreBudgetState = async (previous: Budget | null, created: Budget) => {
    try {
      if (previous) {
        await api.put("/api/v1/budgets", {
          year: previous.year,
          month: previous.month,
          amount: previous.amount,
          alert_threshold_pct: previous.alert_threshold_pct,
        });
      } else {
        await api.delete(`/api/v1/budgets/${created.id}`);
      }
      setFormOpen(false);
      invalidateBudgetViews();
      push({ tone: "info", title: "Budget change undone" });
    } catch {
      push({ tone: "danger", title: "Could not undo the change" });
    }
  };

  const recreateBudget = async (budget: Budget) => {
    try {
      await api.put("/api/v1/budgets", {
        year: budget.year,
        month: budget.month,
        amount: budget.amount,
        alert_threshold_pct: budget.alert_threshold_pct,
      });
      invalidateBudgetViews();
      push({ tone: "info", title: "Budget restored" });
    } catch {
      push({ tone: "danger", title: "Could not restore the budget" });
    }
  };

  const upsertMutation = useMutation({
    mutationFn: ({ form: payload }: { form: BudgetForm; previous: Budget | null }) =>
      api.put<Budget>("/api/v1/budgets", {
        year,
        month: payload.month,
        amount: Number(payload.amount || 0),
        alert_threshold_pct: Number(payload.alert_threshold_pct || 80),
      }),
    onSuccess: (saved, variables) => {
      push({
        tone: "success",
        title: "Budget saved",
        action: {
          label: "Undo",
          onClick: () => void restoreBudgetState(variables.previous, saved),
        },
      });
      setFormOpen(false);
      invalidateBudgetViews();
    },
    onError: (error) =>
      setFormError(error instanceof ApiRequestError ? error.detail : "Could not save the budget."),
  });

  const deleteMutation = useMutation({
    mutationFn: (budget: Budget) => api.delete(`/api/v1/budgets/${budget.id}`),
    onSuccess: (_result, budget) => {
      push({
        tone: "success",
        title: "Budget removed",
        action: { label: "Undo", onClick: () => void recreateBudget(budget) },
      });
      setDeleting(null);
      invalidateBudgetViews();
    },
    onError: () => push({ tone: "danger", title: "Could not remove the budget" }),
  });

  const budgetsByMonth = new Map((budgetsQuery.data ?? []).map((budget) => [budget.month, budget]));

  const openForMonth = (month: number) => {
    const existing = budgetsByMonth.get(month);
    setForm({
      month,
      amount: existing ? String(existing.amount) : "",
      alert_threshold_pct: String(existing?.alert_threshold_pct ?? 80),
    });
    setFormError(null);
    setFormOpen(true);
  };

  const onSubmit = () => {
    setFormError(null);
    const amount = Number(form.amount);
    if (!Number.isFinite(amount) || amount < 0) {
      setFormError("Enter a budget amount of zero or more.");
      return;
    }
    upsertMutation.mutate({ form, previous: budgetsByMonth.get(form.month) ?? null });
  };

  const dashboard = dashboardQuery.data;

  const daysInMonth = new Date(now.year, now.month, 0).getDate();
  const dayOfMonth = Math.min(new Date().getDate(), daysInMonth);
  const pacePct = (dayOfMonth / daysInMonth) * 100;
  const paceExpected = dashboard ? (dashboard.budget_amount * dayOfMonth) / daysInMonth : 0;
  const paceDelta = dashboard ? paceExpected - dashboard.expense_total : 0;

  return (
    <>
      <PageHeader
        title="Budgets"
        subtitle="Monthly limits that keep spending honest."
        actions={
          <Field label="Year" className="w-28">
            {(id) => (
              <Select id={id} value={year} onChange={(event) => setYear(Number(event.target.value))}>
                {Array.from({ length: YEAR_SPAN * 2 + 1 }, (_, index) => now.year - YEAR_SPAN + index).map(
                  (option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ),
                )}
              </Select>
            )}
          </Field>
        }
      />

      {year === now.year && dashboard && dashboard.budget_amount > 0 ? (
        <Card className="mb-5 p-5">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold tracking-wide text-ink-muted uppercase">
                {monthName(now.month)} {now.year} — in progress
              </p>
              <p className="tnum mt-1.5 text-2xl font-semibold">
                {money(dashboard.expense_total, currency, locale)}{" "}
                <span className="text-base font-medium text-ink-muted">
                  of {money(dashboard.budget_amount, currency, locale)} spent
                </span>
              </p>
            </div>
            <div className="flex items-center gap-3">
              <span className="tnum text-sm text-ink-muted">
                {percent(dashboard.utilization_pct, 1)} used
              </span>
              <StatusBadge status={dashboard.status} />
            </div>
          </div>
          <div className="relative mt-4 h-3 rounded-full bg-surface-2">
            <div
              role="progressbar"
              aria-valuenow={Math.min(Math.round(dashboard.utilization_pct), 100)}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="Current month budget utilization"
              className={
                dashboard.status === "over"
                  ? "h-full rounded-full bg-danger"
                  : dashboard.status === "warning"
                    ? "h-full rounded-full bg-warning"
                    : "h-full rounded-full bg-success"
              }
              style={{ width: `${Math.min(dashboard.utilization_pct, 100)}%` }}
            />
            {dayOfMonth < daysInMonth ? (
              <span
                aria-hidden
                className="absolute inset-y-[-3px] w-0.5 rounded-full bg-ink/40"
                style={{ left: `${pacePct}%` }}
              />
            ) : null}
          </div>
          {dayOfMonth < daysInMonth ? (
            <p className="tnum mt-2 text-xs text-ink-muted">
              Day {dayOfMonth} of {daysInMonth} · ≈{money(paceExpected, currency, locale)} expected
              by today ·{" "}
              <span className={paceDelta >= 0 ? "text-success" : "text-warning"}>
                {money(Math.abs(paceDelta), currency, locale)} {paceDelta >= 0 ? "ahead of" : "behind"}{" "}
                pace
              </span>
            </p>
          ) : null}
        </Card>
      ) : null}

      <Card className="overflow-hidden">
        <CardHeader
          title={`${year} plan`}
          subtitle="Set an amount per month — alerts fire at the threshold."
          className="pb-3"
        />
        {budgetsQuery.isLoading ? (
          <LoadingPanel />
        ) : budgetsQuery.isError ? (
          <EmptyState
            icon={<CalendarRange className="size-5" />}
            title="Could not load budgets"
            action={
              <Button variant="secondary" onClick={() => void budgetsQuery.refetch()}>
                Retry
              </Button>
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-y border-line text-left text-xs font-semibold tracking-wide text-ink-muted uppercase">
                  <th scope="col" className="px-5 py-3">
                    Month
                  </th>
                  <th scope="col" className="px-5 py-3 text-right">
                    Budget
                  </th>
                  <th scope="col" className="hidden px-5 py-3 text-right sm:table-cell">
                    Alert threshold
                  </th>
                  <th scope="col" className="px-5 py-3">
                    Status
                  </th>
                  <th scope="col" className="w-32 px-5 py-3">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: 12 }, (_, index) => index + 1).map((month) => {
                  const budget = budgetsByMonth.get(month);
                  const isCurrent = year === now.year && month === now.month;
                  return (
                    <tr
                      key={month}
                      className="border-b border-line/70 last:border-0 hover:bg-surface-2/50"
                    >
                      <td className="px-5 py-3 font-medium">
                        {monthName(month)}
                        {isCurrent ? (
                          <span className="ml-2 text-xs font-semibold text-accent">current</span>
                        ) : null}
                      </td>
                      <td className="tnum px-5 py-3 text-right">
                        {budget ? (
                          money(budget.amount, currency, locale)
                        ) : (
                          <span className="text-ink-muted">Not set</span>
                        )}
                      </td>
                      <td className="tnum hidden px-5 py-3 text-right sm:table-cell">
                        {budget ? (
                          <span className="tnum text-ink-muted">{budget.alert_threshold_pct}%</span>
                        ) : (
                          <span className="text-ink-muted">—</span>
                        )}
                      </td>
                      <td className="px-5 py-3">
                        {isCurrent && dashboard && budget ? (
                          <StatusBadge status={dashboard.status} />
                        ) : budget ? (
                          <span className="text-xs text-ink-muted">Set</span>
                        ) : (
                          <span className="text-xs text-ink-muted">Open</span>
                        )}
                      </td>
                      <td className="px-5 py-3">
                        {canWrite ? (
                          <div className="flex justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              icon={budget ? <Pencil className="size-3.5" /> : <Plus className="size-3.5" />}
                              onClick={() => openForMonth(month)}
                              aria-label={`${budget ? "Edit" : "Set"} budget for ${monthName(month)}`}
                            >
                              {budget ? "Edit" : "Set"}
                            </Button>
                            {budget ? (
                              <button
                                type="button"
                                aria-label={`Remove budget for ${monthName(month)}`}
                                onClick={() => setDeleting(budget)}
                                className="rounded-lg p-1.5 text-ink-muted transition hover:bg-danger-soft hover:text-danger"
                              >
                                <Trash2 className="size-3.5" />
                              </button>
                            ) : null}
                          </div>
                        ) : (
                          <span className="text-xs text-ink-muted">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Dialog
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={`${budgetsByMonth.get(form.month) ? "Edit" : "Set"} budget — ${monthName(form.month)} ${year}`}
        description="Applies to this workspace only."
        footer={
          <>
            <Button variant="secondary" onClick={() => setFormOpen(false)}>
              Cancel
            </Button>
            <Button loading={upsertMutation.isPending} onClick={onSubmit}>
              Save budget
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="Amount">
            {(id) => (
              <Input
                id={id}
                type="number"
                inputMode="decimal"
                min="0"
                step="0.01"
                value={form.amount}
                onChange={(event) => setForm((current) => ({ ...current, amount: event.target.value }))}
                placeholder="0.00"
              />
            )}
          </Field>
          <Field label="Alert threshold (%)" hint="Warn me when this share of the budget is spent.">
            {(id) => (
              <Input
                id={id}
                type="number"
                inputMode="numeric"
                min="1"
                max="100"
                step="1"
                value={form.alert_threshold_pct}
                onChange={(event) =>
                  setForm((current) => ({ ...current, alert_threshold_pct: event.target.value }))
                }
              />
            )}
          </Field>
          {formError ? (
            <p role="alert" className="text-sm font-medium text-danger">
              {formError}
            </p>
          ) : null}
        </div>
      </Dialog>

      <Dialog
        open={Boolean(deleting)}
        onClose={() => setDeleting(null)}
        title="Remove this budget?"
        description="Spending data is kept — only the monthly limit is removed."
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeleting(null)}>
              Keep it
            </Button>
            <Button
              variant="danger"
              loading={deleteMutation.isPending}
              onClick={() => deleting && deleteMutation.mutate(deleting)}
            >
              Remove
            </Button>
          </>
        }
      >
        {deleting ? (
          <p className="text-sm text-ink-muted">
            {monthName(deleting.month)} {deleting.year}:{" "}
            {money(deleting.amount, currency, locale)} limit will be removed.
          </p>
        ) : null}
      </Dialog>
    </>
  );
}
