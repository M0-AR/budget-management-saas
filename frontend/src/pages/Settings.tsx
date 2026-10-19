import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import {
  Archive,
  Check,
  LogOut,
  Moon,
  Palette,
  Pencil,
  Plus,
  Save,
  ShieldCheck,
  Sun,
  SunMoon,
  Tags,
  Trash2,
  Undo2,
  Users,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import { MembersPanel } from "../components/MembersPanel";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Dialog,
  Field,
  Input,
  LoadingPanel,
  PageHeader,
  useToast,
} from "../components/ui";
import { api, ApiRequestError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useTheme, type ThemeMode } from "../lib/theme";
import type { Category, CategoryKind, SettingsUpdate, TenantOut, TenantSettings } from "../lib/types";
import { cn } from "../lib/utils";

const CURRENCIES = [
  "USD", "EUR", "GBP", "TRY", "AED", "SAR", "EGP", "INR", "JPY", "CAD", "AUD",
  "CHF", "SEK", "NOK", "DKK", "PLN", "BRL", "MXN", "ZAR", "NGN", "KES", "SGD",
  "HKD", "CNY",
];

const LOCALES = [
  "en-US", "en-GB", "de-DE", "fr-FR", "es-ES", "it-IT", "pt-BR", "nl-NL",
  "tr-TR", "ar-AE", "ja-JP", "zh-CN",
];

const FALLBACK_TIMEZONES = [
  "UTC", "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
  "America/Sao_Paulo", "Europe/London", "Europe/Paris", "Europe/Berlin", "Europe/Istanbul",
  "Africa/Cairo", "Africa/Lagos", "Asia/Dubai", "Asia/Riyadh", "Asia/Karachi", "Asia/Kolkata",
  "Asia/Singapore", "Asia/Tokyo", "Australia/Sydney",
];

function timezoneOptions(): string[] {
  try {
    const supported = (Intl as unknown as { supportedValuesOf?: (key: string) => string[] })
      .supportedValuesOf?.("timeZone");
    if (Array.isArray(supported) && supported.length > 0) {
      return supported.includes("UTC") ? supported : ["UTC", ...supported];
    }
  } catch {
    /* not supported in this browser */
  }
  return FALLBACK_TIMEZONES;
}

type Tab = "workspace" | "categories" | "members" | "preferences";

export function SettingsPage() {
  const { tenant, user, updateTenant, logout } = useAuth();
  const { mode, setMode } = useTheme();
  const { push } = useToast();
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const [tab, setTab] = useState<Tab>("workspace");

  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: () => api.get<TenantSettings>("/api/v1/settings"),
  });

  const [form, setForm] = useState<SettingsUpdate>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!settingsQuery.data) return;
    setForm({
      display_name: settingsQuery.data.display_name,
      accent_color: settingsQuery.data.accent_color ?? "#4f46e5",
      logo_url: settingsQuery.data.logo_url ?? "",
      currency: settingsQuery.data.currency,
      locale: settingsQuery.data.locale,
      timezone: settingsQuery.data.timezone,
    });
  }, [settingsQuery.data]);

  const canEdit = settingsQuery.data?.role === "owner" || settingsQuery.data?.role === "admin";
  const timezones = useMemo(() => {
    const base = timezoneOptions();
    const current = settingsQuery.data?.timezone;
    return current && !base.includes(current) ? [current, ...base] : base;
  }, [settingsQuery.data?.timezone]);

  const saveMutation = useMutation({
    mutationFn: (payload: SettingsUpdate) => api.put<TenantSettings>("/api/v1/settings", payload),
    onSuccess: (updated) => {
      push({ tone: "success", title: "Workspace updated" });
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
      if (tenant) {
        const merged: TenantOut = {
          ...tenant,
          name: updated.name,
          currency: updated.currency,
          locale: updated.locale,
          timezone: updated.timezone,
          branding: {
            ...tenant.branding,
            accent_color: updated.accent_color,
            display_name: updated.display_name,
            logo_url: updated.logo_url,
          },
        };
        updateTenant(merged);
      }
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (caught) =>
      setError(caught instanceof ApiRequestError ? caught.detail : "Could not save the settings."),
  });

  const onSubmit = () => {
    setError(null);
    if (!form.display_name || form.display_name.trim().length === 0) {
      setError("Display name cannot be empty.");
      return;
    }
    if (form.accent_color && !/^#[0-9a-fA-F]{6}$/.test(form.accent_color)) {
      setError("Accent colour must be a 6-digit hex value like #4f46e5.");
      return;
    }
    const payload: SettingsUpdate = {
      display_name: form.display_name?.trim(),
      accent_color: form.accent_color,
      currency: form.currency,
      locale: form.locale,
      timezone: form.timezone,
      logo_url: form.logo_url?.trim() || undefined,
    };
    saveMutation.mutate(payload);
  };

  const canManageCategories = user?.role !== "viewer";

  const categoriesQuery = useQuery({
    queryKey: ["categories", "settings"],
    queryFn: () => api.get<Category[]>("/api/v1/categories?include_archived=true"),
  });

  const [newCategory, setNewCategory] = useState<{
    name: string;
    kind: CategoryKind;
    color: string;
  }>({ name: "", kind: "expense", color: "#64748b" });
  const [categoryError, setCategoryError] = useState<string | null>(null);
  const [editingCategory, setEditingCategory] = useState<Category | null>(null);
  const [editForm, setEditForm] = useState({ name: "", color: "#64748b" });
  const [deletingCategory, setDeletingCategory] = useState<Category | null>(null);

  const invalidateCategoryViews = () => {
    void queryClient.invalidateQueries({ queryKey: ["categories"] });
    void queryClient.invalidateQueries({ queryKey: ["transactions"] });
    void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    void queryClient.invalidateQueries({ queryKey: ["reports"] });
  };

  const createCategoryMutation = useMutation({
    mutationFn: () =>
      api.post<Category>("/api/v1/categories", {
        name: newCategory.name.trim(),
        kind: newCategory.kind,
        color: newCategory.color,
      }),
    onSuccess: (created) => {
      push({ tone: "success", title: `Category "${created.name}" added` });
      setNewCategory((current) => ({ ...current, name: "" }));
      setCategoryError(null);
      invalidateCategoryViews();
    },
    onError: (caught) =>
      setCategoryError(
        caught instanceof ApiRequestError ? caught.detail : "Could not add the category.",
      ),
  });

  const updateCategoryMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Record<string, unknown> }) =>
      api.put<Category>(`/api/v1/categories/${id}`, payload),
    onSuccess: () => {
      push({ tone: "success", title: "Category updated" });
      setEditingCategory(null);
      setCategoryError(null);
      invalidateCategoryViews();
    },
    onError: (caught) =>
      setCategoryError(
        caught instanceof ApiRequestError ? caught.detail : "Could not update the category.",
      ),
  });

  const deleteCategoryMutation = useMutation({
    mutationFn: (category: Category) => api.delete(`/api/v1/categories/${category.id}`),
    onSuccess: () => {
      push({ tone: "success", title: "Category removed" });
      setDeletingCategory(null);
      invalidateCategoryViews();
    },
    onError: (caught) =>
      push({
        tone: "danger",
        title: caught instanceof ApiRequestError ? caught.detail : "Could not remove the category",
      }),
  });

  const saveCategoryEdit = () => {
    if (!editingCategory) return;
    updateCategoryMutation.mutate({
      id: editingCategory.id,
      payload: { name: editForm.name.trim(), color: editForm.color },
    });
  };

  const accentPreview = /^#[0-9a-fA-F]{6}$/.test(form.accent_color ?? "") ? form.accent_color! : "#4f46e5";

  return (
    <>
      <PageHeader title="Settings" subtitle="Workspace branding, regional formats and your preferences." />

      <div className="mb-5 flex gap-1 rounded-xl border border-line bg-surface-1 p-1 sm:w-fit" role="tablist">
        {(
          [
            { id: "workspace", label: "Workspace", icon: Palette },
            { id: "categories", label: "Categories", icon: Tags },
            { id: "members", label: "Members", icon: Users },
            { id: "preferences", label: "Preferences", icon: ShieldCheck },
          ] as const
        ).map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={cn(
              "flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition sm:flex-none",
              tab === id ? "bg-surface-2 text-ink" : "text-ink-muted hover:bg-surface-2 hover:text-ink",
            )}
          >
            <Icon className="size-4" aria-hidden />
            {label}
          </button>
        ))}
      </div>

      {tab === "workspace" ? (
        settingsQuery.isLoading ? (
          <Card>
            <LoadingPanel />
          </Card>
        ) : settingsQuery.isError || !settingsQuery.data ? (
          <Card>
            <div className="p-6 text-sm text-ink-muted">
              Could not load settings.{" "}
              <button className="font-semibold text-accent" onClick={() => void settingsQuery.refetch()}>
                Retry
              </button>
            </div>
          </Card>
        ) : (
          <div className="grid gap-5 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader
                title="Branding & regional defaults"
                subtitle="Applied to every member of this workspace."
                action={!canEdit ? <Badge tone="warning">Read-only for your role</Badge> : null}
              />
              <div className="space-y-5 p-5">
                <Field label="Display name" hint="Shown on the sign-in page and in the app header.">
                  {(id) => (
                    <Input
                      id={id}
                      value={form.display_name ?? ""}
                      disabled={!canEdit}
                      maxLength={60}
                      onChange={(event) =>
                        setForm((current) => ({ ...current, display_name: event.target.value }))
                      }
                    />
                  )}
                </Field>

                <div className="grid gap-5 sm:grid-cols-2">
                  <Field label="Accent colour" hint="Pick a colour or paste a hex value.">
                    {(id) => (
                      <div className="flex items-center gap-2">
                        <input
                          id={id}
                          type="color"
                          value={accentPreview}
                          disabled={!canEdit}
                          onChange={(event) =>
                            setForm((current) => ({ ...current, accent_color: event.target.value }))
                          }
                          className="size-10 cursor-pointer rounded-xl border border-line bg-surface-1 p-1"
                          aria-label="Accent colour picker"
                        />
                        <Input
                          value={form.accent_color ?? ""}
                          disabled={!canEdit}
                          pattern="^#[0-9a-fA-F]{6}$"
                          placeholder="#4f46e5"
                          onChange={(event) =>
                            setForm((current) => ({ ...current, accent_color: event.target.value }))
                          }
                        />
                      </div>
                    )}
                  </Field>

                  <Field label="Logo URL" hint="Optional — https link to your logo.">
                    {(id) => (
                      <Input
                        id={id}
                        type="url"
                        value={form.logo_url ?? ""}
                        disabled={!canEdit}
                        placeholder="https://…"
                        onChange={(event) =>
                          setForm((current) => ({ ...current, logo_url: event.target.value }))
                        }
                      />
                    )}
                  </Field>
                </div>

                <div className="grid gap-5 sm:grid-cols-3">
                  <Field label="Currency">
                    {(id) => (
                      <select
                        id={id}
                        value={form.currency ?? "USD"}
                        disabled={!canEdit}
                        onChange={(event) =>
                          setForm((current) => ({ ...current, currency: event.target.value }))
                        }
                        className="w-full rounded-xl border border-line bg-surface-1 px-3.5 py-2.5 text-sm"
                      >
                        {CURRENCIES.map((code) => (
                          <option key={code} value={code}>
                            {code}
                          </option>
                        ))}
                      </select>
                    )}
                  </Field>
                  <Field label="Locale">
                    {(id) => (
                      <select
                        id={id}
                        value={form.locale ?? "en-US"}
                        disabled={!canEdit}
                        onChange={(event) =>
                          setForm((current) => ({ ...current, locale: event.target.value }))
                        }
                        className="w-full rounded-xl border border-line bg-surface-1 px-3.5 py-2.5 text-sm"
                      >
                        {LOCALES.map((code) => (
                          <option key={code} value={code}>
                            {code}
                          </option>
                        ))}
                      </select>
                    )}
                  </Field>
                  <Field label="Timezone">
                    {(id) => (
                      <select
                        id={id}
                        value={form.timezone ?? "UTC"}
                        disabled={!canEdit}
                        onChange={(event) =>
                          setForm((current) => ({ ...current, timezone: event.target.value }))
                        }
                        className="w-full rounded-xl border border-line bg-surface-1 px-3.5 py-2.5 text-sm"
                      >
                        {timezones.map((zone) => (
                          <option key={zone} value={zone}>
                            {zone}
                          </option>
                        ))}
                      </select>
                    )}
                  </Field>
                </div>

                {error ? (
                  <p role="alert" className="text-sm font-medium text-danger">
                    {error}
                  </p>
                ) : null}

                {canEdit ? (
                  <div className="flex justify-end">
                    <Button
                      icon={<Save className="size-4" />}
                      loading={saveMutation.isPending}
                      onClick={onSubmit}
                    >
                      Save changes
                    </Button>
                  </div>
                ) : null}
              </div>
            </Card>

            <Card className="h-fit">
              <CardHeader title="Preview" subtitle="How your workspace accent looks." />
              <div className="space-y-4 p-5">
                <div
                  className="rounded-2xl p-5 text-white shadow-sm"
                  style={{ background: accentPreview }}
                >
                  <p className="text-sm font-semibold opacity-90">
                    {form.display_name || tenant?.name}
                  </p>
                  <p className="mt-2 text-2xl font-semibold">{tenant ? "Budget" : "Budget"}ary</p>
                  <p className="mt-1 text-xs opacity-80">Workspace /{settingsQuery.data.slug}</p>
                </div>
                <dl className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-ink-muted">Tier</dt>
                    <dd>
                      <Badge tone="neutral">{settingsQuery.data.tier}</Badge>
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-ink-muted">Your role</dt>
                    <dd className="font-medium capitalize">{settingsQuery.data.role}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-ink-muted">Currency / locale</dt>
                    <dd className="tnum font-medium">
                      {form.currency} · {form.locale}
                    </dd>
                  </div>
                </dl>
              </div>
            </Card>
          </div>
        )
      ) : tab === "categories" ? (
        <Card>
          <CardHeader
            title="Categories"
            subtitle="Group expenses and income. Rename, recolour, archive or remove categories — history stays intact."
            action={
              !canManageCategories ? <Badge tone="warning">Read-only for your role</Badge> : null
            }
          />
          {categoriesQuery.isLoading ? (
            <LoadingPanel label="Loading categories…" />
          ) : categoriesQuery.isError || !categoriesQuery.data ? (
            <div className="p-5 text-sm text-ink-muted">
              Could not load categories.{" "}
              <button
                className="font-semibold text-accent"
                onClick={() => void categoriesQuery.refetch()}
              >
                Retry
              </button>
            </div>
          ) : (
            <div className="space-y-6 p-5">
              {(["expense", "income"] as const).map((kind) => {
                const group = categoriesQuery.data
                  .filter((category) => category.kind === kind)
                  .sort(
                    (a, b) =>
                      Number(a.is_archived) - Number(b.is_archived) ||
                      a.name.localeCompare(b.name),
                  );
                return (
                  <section key={kind}>
                    <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                      {kind === "expense" ? "Expense categories" : "Income categories"}
                    </h3>
                    {group.length === 0 ? (
                      <p className="rounded-xl border border-dashed border-line px-4 py-3 text-sm text-ink-muted">
                        No {kind} categories yet.
                      </p>
                    ) : (
                      <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line">
                        {group.map((category) => (
                          <li
                            key={category.id}
                            className="flex flex-wrap items-center gap-3 px-4 py-2.5"
                          >
                            {editingCategory?.id === category.id ? (
                              <>
                                <input
                                  type="color"
                                  value={editForm.color}
                                  aria-label={`Colour for ${category.name}`}
                                  onChange={(event) =>
                                    setEditForm((current) => ({
                                      ...current,
                                      color: event.target.value,
                                    }))
                                  }
                                  className="size-9 shrink-0 cursor-pointer rounded-lg border border-line bg-surface-1 p-1"
                                />
                                <Input
                                  value={editForm.name}
                                  aria-label={`Name for ${category.name}`}
                                  maxLength={80}
                                  autoFocus
                                  onChange={(event) =>
                                    setEditForm((current) => ({
                                      ...current,
                                      name: event.target.value,
                                    }))
                                  }
                                  onKeyDown={(event) => {
                                    if (event.key === "Enter") saveCategoryEdit();
                                    if (event.key === "Escape") setEditingCategory(null);
                                  }}
                                  className="min-w-40 flex-1"
                                />
                                <Button
                                  size="sm"
                                  variant="secondary"
                                  onClick={() => setEditingCategory(null)}
                                >
                                  Cancel
                                </Button>
                                <Button
                                  size="sm"
                                  icon={<Check className="size-4" />}
                                  disabled={editForm.name.trim().length === 0}
                                  loading={updateCategoryMutation.isPending}
                                  onClick={saveCategoryEdit}
                                >
                                  Save
                                </Button>
                              </>
                            ) : (
                              <>
                                <span
                                  className="size-3 shrink-0 rounded-full border border-line"
                                  style={{ background: category.color }}
                                  aria-hidden
                                />
                                <span
                                  className={cn(
                                    "flex-1 text-sm",
                                    category.is_archived && "text-ink-muted line-through",
                                  )}
                                >
                                  {category.name}
                                </span>
                                {category.is_archived ? (
                                  <Badge tone="neutral">Archived</Badge>
                                ) : null}
                                {canManageCategories ? (
                                  <div className="flex items-center gap-1">
                                    <button
                                      type="button"
                                      aria-label={`Edit ${category.name}`}
                                      onClick={() => {
                                        setEditingCategory(category);
                                        setEditForm({ name: category.name, color: category.color });
                                      }}
                                      className="rounded-lg p-1.5 text-ink-muted transition hover:bg-surface-2 hover:text-ink"
                                    >
                                      <Pencil className="size-4" />
                                    </button>
                                    <button
                                      type="button"
                                      aria-label={
                                        category.is_archived
                                          ? `Restore ${category.name}`
                                          : `Archive ${category.name}`
                                      }
                                      onClick={() =>
                                        updateCategoryMutation.mutate({
                                          id: category.id,
                                          payload: { is_archived: !category.is_archived },
                                        })
                                      }
                                      className="rounded-lg p-1.5 text-ink-muted transition hover:bg-surface-2 hover:text-ink"
                                    >
                                      {category.is_archived ? (
                                        <Undo2 className="size-4" />
                                      ) : (
                                        <Archive className="size-4" />
                                      )}
                                    </button>
                                    <button
                                      type="button"
                                      aria-label={`Delete ${category.name}`}
                                      onClick={() => setDeletingCategory(category)}
                                      className="rounded-lg p-1.5 text-ink-muted transition hover:bg-surface-2 hover:text-danger"
                                    >
                                      <Trash2 className="size-4" />
                                    </button>
                                  </div>
                                ) : null}
                              </>
                            )}
                          </li>
                        ))}
                      </ul>
                    )}
                  </section>
                );
              })}

              {canManageCategories ? (
                <div className="border-t border-line pt-5">
                  <p className="mb-3 text-sm font-medium">Add category</p>
                  <div className="flex flex-wrap items-center gap-3">
                    <input
                      type="color"
                      value={newCategory.color}
                      aria-label="New category colour"
                      onChange={(event) =>
                        setNewCategory((current) => ({ ...current, color: event.target.value }))
                      }
                      className="size-10 shrink-0 cursor-pointer rounded-xl border border-line bg-surface-1 p-1"
                    />
                    <Input
                      value={newCategory.name}
                      aria-label="New category name"
                      placeholder="e.g. Subscriptions"
                      maxLength={80}
                      onChange={(event) => {
                        setCategoryError(null);
                        setNewCategory((current) => ({ ...current, name: event.target.value }));
                      }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" && newCategory.name.trim().length > 0) {
                          createCategoryMutation.mutate();
                        }
                      }}
                      className="w-full sm:w-56"
                    />
                    <select
                      value={newCategory.kind}
                      aria-label="New category kind"
                      onChange={(event) => {
                        setCategoryError(null);
                        setNewCategory((current) => ({
                          ...current,
                          kind: event.target.value as CategoryKind,
                        }));
                      }}
                      className="h-10 rounded-xl border border-line bg-surface-1 px-3.5 text-sm"
                    >
                      <option value="expense">Expense</option>
                      <option value="income">Income</option>
                    </select>
                    <Button
                      icon={<Plus className="size-4" />}
                      disabled={newCategory.name.trim().length === 0}
                      loading={createCategoryMutation.isPending}
                      onClick={() => createCategoryMutation.mutate()}
                    >
                      Add
                    </Button>
                  </div>
                  {categoryError ? (
                    <p role="alert" className="mt-2 text-sm font-medium text-danger">
                      {categoryError}
                    </p>
                  ) : null}
                </div>
              ) : null}
            </div>
          )}
        </Card>
      ) : tab === "members" ? (
        <MembersPanel />
      ) : (
        <div className="grid gap-5 lg:grid-cols-2">
          <Card>
            <CardHeader title="Appearance" subtitle="Choose how Budgetary looks on this device." />
            <div className="space-y-2 p-5">
              {(
                [
                  { id: "light", label: "Light", icon: Sun, description: "Always light" },
                  { id: "dark", label: "Dark", icon: Moon, description: "Always dark" },
                  { id: "system", label: "System", icon: SunMoon, description: "Follow the OS" },
                ] as const
              ).map(({ id, label, icon: Icon, description }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setMode(id as ThemeMode)}
                  aria-pressed={mode === id}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left transition",
                    mode === id
                      ? "border-accent bg-accent-soft"
                      : "border-line hover:bg-surface-2",
                  )}
                >
                  <Icon className={cn("size-4", mode === id ? "text-accent" : "text-ink-muted")} aria-hidden />
                  <span className="flex-1">
                    <span className="block text-sm font-medium">{label}</span>
                    <span className="block text-xs text-ink-muted">{description}</span>
                  </span>
                  {mode === id ? <Badge tone="success">Active</Badge> : null}
                </button>
              ))}
            </div>
          </Card>

          <Card>
            <CardHeader title="Account" subtitle="Your membership in this workspace." />
            <div className="space-y-4 p-5">
              <dl className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <dt className="text-ink-muted">Name</dt>
                  <dd className="font-medium">{user?.full_name || "—"}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-ink-muted">Email</dt>
                  <dd className="font-medium">{user?.email}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-ink-muted">Role</dt>
                  <dd>
                    <Badge tone="neutral">{user?.role}</Badge>
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-ink-muted">Workspace</dt>
                  <dd className="font-medium">/{tenant?.slug}</dd>
                </div>
              </dl>
              <div className="border-t border-line pt-4">
                <Button
                  variant="secondary"
                  icon={<LogOut className="size-4" />}
                  onClick={() => {
                    logout();
                    navigate("/login", { replace: true });
                  }}
                >
                  Sign out
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}

      <Dialog
        open={Boolean(deletingCategory)}
        onClose={() => setDeletingCategory(null)}
        title="Remove this category?"
        description="Transactions using it are kept and become uncategorized."
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeletingCategory(null)}>
              Keep it
            </Button>
            <Button
              variant="danger"
              loading={deleteCategoryMutation.isPending}
              onClick={() => deletingCategory && deleteCategoryMutation.mutate(deletingCategory)}
            >
              Remove
            </Button>
          </>
        }
      >
        {deletingCategory ? (
          <p className="text-sm text-ink-muted">
            "{deletingCategory.name}" will no longer appear in pickers, reports or new
            transactions.
          </p>
        ) : null}
      </Dialog>
    </>
  );
}
