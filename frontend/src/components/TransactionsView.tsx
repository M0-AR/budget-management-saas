import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Download, Pencil, Plus, ReceiptText, Search, Trash2, Upload } from "lucide-react";

import { api, buildQuery, downloadFile, ApiRequestError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { formatDate, money, monthName, todayIso } from "../lib/format";
import type { Category, Transaction, TransactionPage } from "../lib/types";
import { ImportCsvDialog } from "./ImportCsvDialog";
import {
  Button,
  Card,
  Dialog,
  EmptyState,
  Field,
  Input,
  LoadingPanel,
  Select,
  Textarea,
  useToast,
} from "./ui";

type Kind = "expense" | "income";

interface FormState {
  amount: string;
  category_id: string;
  note: string;
  happened_on: string;
}

const EMPTY_FORM: FormState = { amount: "", category_id: "", note: "", happened_on: todayIso() };

const YEAR_SPAN = 3;

export function TransactionsView({ kind }: { kind: Kind }) {
  const { tenant, user } = useAuth();
  const queryClient = useQueryClient();
  const { push } = useToast();

  const currency = tenant?.currency ?? "USD";
  const locale = tenant?.locale ?? "en-US";
  const canWrite = user?.role !== "viewer";
  const plural = kind === "expense" ? "expenses" : "income entries";
  const endpoint = kind === "expense" ? "/api/v1/expenses" : "/api/v1/incomes";
  const currentYear = new Date().getFullYear();

  const [year, setYear] = useState<number>(currentYear);
  const [month, setMonth] = useState<number>(new Date().getMonth() + 1);
  const [allYear, setAllYear] = useState(false);
  const [categoryId, setCategoryId] = useState("");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [page, setPage] = useState(1);

  const [editing, setEditing] = useState<Transaction | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<Transaction | null>(null);
  const [importOpen, setImportOpen] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearch(search.trim());
      setPage(1);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  const categoriesQuery = useQuery({
    queryKey: ["categories", kind],
    queryFn: () => api.get<Category[]>(`/api/v1/categories?kind=${kind}`),
  });

  const listQuery = useQuery({
    queryKey: ["transactions", kind, year, allYear ? "all" : month, categoryId, debouncedSearch, page],
    queryFn: () =>
      api.get<TransactionPage>(
        `${endpoint}${buildQuery({
          year,
          month: allYear ? undefined : month,
          category_id: categoryId || undefined,
          q: debouncedSearch || undefined,
          page,
          page_size: 20,
        })}`,
      ),
  });

  const categories = useMemo(
    () => (categoriesQuery.data ?? []).filter((category) => !category.is_archived),
    [categoriesQuery.data],
  );

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["transactions", kind] });
    void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    void queryClient.invalidateQueries({ queryKey: ["reports"] });
  };

  const saveMutation = useMutation({
    mutationFn: async (payload: FormState) => {
      const body = {
        amount: Number(payload.amount),
        category_id: payload.category_id || null,
        note: payload.note.trim(),
        happened_on: payload.happened_on,
      };
      if (editing) return api.put<Transaction>(`${endpoint}/${editing.id}`, body);
      return api.post<Transaction>(endpoint, body);
    },
    onSuccess: () => {
      push({ tone: "success", title: editing ? "Entry updated" : `Entry added to ${plural}` });
      setFormOpen(false);
      setEditing(null);
      setForm(EMPTY_FORM);
      invalidate();
    },
    onError: (error) => {
      setFormError(error instanceof ApiRequestError ? error.detail : "Could not save the entry.");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (transaction: Transaction) => api.delete(`${endpoint}/${transaction.id}`),
    onSuccess: () => {
      push({ tone: "success", title: "Entry deleted" });
      setDeleting(null);
      invalidate();
    },
    onError: () => push({ tone: "danger", title: "Could not delete the entry" }),
  });

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setFormError(null);
    setFormOpen(true);
  };

  const openEdit = (transaction: Transaction) => {
    setEditing(transaction);
    setForm({
      amount: String(transaction.amount),
      category_id: transaction.category_id ?? "",
      note: transaction.note,
      happened_on: transaction.happened_on,
    });
    setFormError(null);
    setFormOpen(true);
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    setFormError(null);
    const amount = Number(form.amount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setFormError("Enter an amount greater than zero.");
      return;
    }
    if (!form.happened_on) {
      setFormError("Pick the date this happened.");
      return;
    }
    saveMutation.mutate(form);
  };

  const onExport = async () => {
    try {
      await downloadFile(
        `/api/v1/exports/transactions.csv${buildQuery({ year, month })}`,
        `transactions-${year}-${String(month).padStart(2, "0")}.csv`,
      );
    } catch {
      push({ tone: "danger", title: "Export failed", description: "Please try again." });
    }
  };

  const data = listQuery.data;
  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-end gap-3 p-4">
          <Field label="Year" className="w-28">
            {(id) => (
              <Select
                id={id}
                value={year}
                onChange={(event) => {
                  setYear(Number(event.target.value));
                  setPage(1);
                }}
              >
                {Array.from({ length: YEAR_SPAN * 2 + 1 }, (_, index) => currentYear - YEAR_SPAN + index).map(
                  (option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ),
                )}
              </Select>
            )}
          </Field>

          <Field label="Month" className="w-40">
            {(id) => (
              <Select
                id={id}
                value={allYear ? "all" : String(month)}
                onChange={(event) => {
                  if (event.target.value === "all") setAllYear(true);
                  else {
                    setAllYear(false);
                    setMonth(Number(event.target.value));
                  }
                  setPage(1);
                }}
              >
                <option value="all">All months</option>
                {Array.from({ length: 12 }, (_, index) => index + 1).map((option) => (
                  <option key={option} value={option}>
                    {monthName(option)}
                  </option>
                ))}
              </Select>
            )}
          </Field>

          <Field label="Category" className="w-48">
            {(id) => (
              <Select
                id={id}
                value={categoryId}
                onChange={(event) => {
                  setCategoryId(event.target.value);
                  setPage(1);
                }}
              >
                <option value="">All categories</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>

          <Field label="Search" className="min-w-44 flex-1">
            {(id) => (
              <div className="relative">
                <Search
                  className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-muted"
                  aria-hidden
                />
                <Input
                  id={id}
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search notes…"
                  className="pl-9"
                />
              </div>
            )}
          </Field>

          <div className="flex gap-2 pb-0.5">
            <Button variant="secondary" icon={<Download className="size-4" />} onClick={onExport}>
              CSV
            </Button>
            {canWrite ? (
              <Button
                variant="secondary"
                icon={<Upload className="size-4" />}
                onClick={() => setImportOpen(true)}
              >
                Import
              </Button>
            ) : null}
            {canWrite ? (
              <Button icon={<Plus className="size-4" />} onClick={openCreate}>
                Add
              </Button>
            ) : null}
          </div>
        </div>
      </Card>

      <Card className="overflow-hidden">
        {listQuery.isLoading ? (
          <LoadingPanel />
        ) : listQuery.isError ? (
          <EmptyState
            icon={<ReceiptText className="size-5" />}
            title="Could not load your data"
            description="Check your connection and try again."
            action={
              <Button variant="secondary" onClick={() => void listQuery.refetch()}>
                Retry
              </Button>
            }
          />
        ) : data && data.items.length === 0 ? (
          <EmptyState
            icon={<ReceiptText className="size-5" />}
            title={`No ${plural} for this period`}
            description="Adjust the filters, or add your first entry."
            action={
              canWrite ? (
                <Button icon={<Plus className="size-4" />} onClick={openCreate}>
                  Add {kind === "expense" ? "expense" : "income"}
                </Button>
              ) : undefined
            }
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs font-semibold tracking-wide text-ink-muted uppercase">
                    <th scope="col" className="px-5 py-3">
                      Date
                    </th>
                    <th scope="col" className="px-5 py-3">
                      Category
                    </th>
                    <th scope="col" className="hidden px-5 py-3 sm:table-cell">
                      Note
                    </th>
                    <th scope="col" className="px-5 py-3 text-right">
                      Amount
                    </th>
                    <th scope="col" className="w-24 px-5 py-3">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data?.items.map((transaction) => (
                    <tr
                      key={transaction.id}
                      className="border-b border-line/70 transition-colors last:border-0 hover:bg-surface-2/60"
                    >
                      <td className="tnum px-5 py-3 whitespace-nowrap text-ink-muted">
                        {formatDate(transaction.happened_on, locale)}
                      </td>
                      <td className="px-5 py-3">
                        {transaction.category_name ? (
                          <span className="inline-flex items-center gap-2">
                            <span
                              aria-hidden
                              className="size-2 rounded-full"
                              style={{ background: transaction.category_color ?? "#64748b" }}
                            />
                            {transaction.category_name}
                          </span>
                        ) : (
                          <span className="text-ink-muted">Uncategorized</span>
                        )}
                      </td>
                      <td className="hidden max-w-64 truncate px-5 py-3 text-ink-muted sm:table-cell">
                        {transaction.note || "—"}
                      </td>
                      <td className="tnum px-5 py-3 text-right font-semibold whitespace-nowrap">
                        {money(transaction.amount, currency, locale)}
                      </td>
                      <td className="px-5 py-3">
                        {canWrite ? (
                          <div className="flex justify-end gap-1">
                            <button
                              type="button"
                              aria-label={`Edit entry from ${transaction.happened_on}`}
                              onClick={() => openEdit(transaction)}
                              className="rounded-lg p-1.5 text-ink-muted transition hover:bg-surface-2 hover:text-ink"
                            >
                              <Pencil className="size-3.5" />
                            </button>
                            <button
                              type="button"
                              aria-label={`Delete entry from ${transaction.happened_on}`}
                              onClick={() => setDeleting(transaction)}
                              className="rounded-lg p-1.5 text-ink-muted transition hover:bg-danger-soft hover:text-danger"
                            >
                              <Trash2 className="size-3.5" />
                            </button>
                          </div>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-5 py-3.5 text-sm">
              <p className="text-ink-muted">
                <span className="tnum font-semibold text-ink">
                  {money(data?.filtered_amount ?? 0, currency, locale)}
                </span>{" "}
                across {data?.total ?? 0} {data?.total === 1 ? "entry" : "entries"}
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                >
                  Previous
                </Button>
                <span className="tnum text-xs text-ink-muted">
                  {page} / {totalPages}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((current) => current + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        )}
      </Card>

      <Dialog
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editing ? `Edit ${kind}` : `Add ${kind}`}
        description={editing ? "Update the entry and save." : "Record a new entry for this workspace."}
        footer={
          <>
            <Button variant="secondary" onClick={() => setFormOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" form="transaction-form" loading={saveMutation.isPending}>
              {editing ? "Save changes" : "Add entry"}
            </Button>
          </>
        }
      >
        <form id="transaction-form" onSubmit={onSubmit} className="space-y-4" noValidate>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Amount" error={formError && !Number(form.amount) ? formError : null}>
              {(id) => (
                <Input
                  id={id}
                  type="number"
                  inputMode="decimal"
                  min="0.01"
                  step="0.01"
                  value={form.amount}
                  onChange={(event) => setForm((current) => ({ ...current, amount: event.target.value }))}
                  placeholder="0.00"
                  required
                />
              )}
            </Field>
            <Field label="Date">
              {(id) => (
                <Input
                  id={id}
                  type="date"
                  value={form.happened_on}
                  max={todayIso()}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, happened_on: event.target.value }))
                  }
                  required
                />
              )}
            </Field>
          </div>

          <Field label="Category">
            {(id) => (
              <Select
                id={id}
                value={form.category_id}
                onChange={(event) =>
                  setForm((current) => ({ ...current, category_id: event.target.value }))
                }
              >
                <option value="">Uncategorized</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>

          <Field label="Note" hint="Optional, up to 500 characters.">
            {(id) => (
              <Textarea
                id={id}
                value={form.note}
                onChange={(event) => setForm((current) => ({ ...current, note: event.target.value }))}
                placeholder="What was this for?"
                maxLength={500}
              />
            )}
          </Field>

          {formError ? (
            <p role="alert" className="text-sm font-medium text-danger">
              {formError}
            </p>
          ) : null}
        </form>
      </Dialog>

      <ImportCsvDialog kind={kind} open={importOpen} onClose={() => setImportOpen(false)} />

      <Dialog
        open={Boolean(deleting)}
        onClose={() => setDeleting(null)}
        title={`Delete this ${kind}?`}
        description="This cannot be undone."
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
              Delete
            </Button>
          </>
        }
      >
        {deleting ? (
          <p className="text-sm text-ink-muted">
            {money(deleting.amount, currency, locale)} on {formatDate(deleting.happened_on, locale)}
            {deleting.note ? ` — “${deleting.note}”` : ""} will be permanently removed.
          </p>
        ) : null}
      </Dialog>
    </div>
  );
}
