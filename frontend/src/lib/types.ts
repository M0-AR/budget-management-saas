export type Role = "owner" | "admin" | "member" | "viewer";
export type AssignableRole = Exclude<Role, "owner">;
export type CategoryKind = "expense" | "income";
export type BudgetStatus = "no_budget" | "on_track" | "warning" | "over";

export interface Member {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  created_at: string;
}

export interface Invite {
  id: string;
  email: string;
  role: AssignableRole;
  expires_at: string;
  created_at: string;
}

export interface InviteCreated extends Invite {
  /** Plaintext token — exposed by the API exactly once, at creation. */
  token: string;
}

export interface UserOut {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  tenant_id: string;
}

export interface TenantOut {
  id: string;
  slug: string;
  name: string;
  tier: string;
  currency: string;
  locale: string;
  timezone: string;
  branding: Record<string, unknown>;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface AuthResponse {
  user: UserOut;
  tenant: TenantOut;
  tokens: TokenPair;
}

export interface MeOut {
  user: UserOut;
  tenant: TenantOut;
}

export interface PublicBranding {
  slug: string;
  display_name: string;
  accent_color: string | null;
  logo_url: string | null;
  currency: string;
  locale: string;
}

export interface TenantSettings {
  slug: string;
  name: string;
  display_name: string;
  accent_color: string | null;
  logo_url: string | null;
  currency: string;
  locale: string;
  timezone: string;
  tier: string;
  role: Role;
}

export interface SettingsUpdate {
  display_name?: string;
  accent_color?: string;
  logo_url?: string;
  currency?: string;
  locale?: string;
  timezone?: string;
}

export interface Category {
  id: string;
  name: string;
  kind: CategoryKind;
  color: string;
  is_archived: boolean;
}

export interface Budget {
  id: string;
  year: number;
  month: number;
  amount: number;
  alert_threshold_pct: number;
}

export interface Transaction {
  id: string;
  amount: number;
  category_id: string | null;
  category_name: string | null;
  category_color: string | null;
  note: string;
  happened_on: string;
  created_at: string;
}

export interface TransactionPage {
  items: Transaction[];
  total: number;
  page: number;
  page_size: number;
  filtered_amount: number;
}

export interface ImportRowError {
  row: number;
  message: string;
}

export interface ImportSummary {
  imported_expenses: number;
  imported_incomes: number;
  duplicates_skipped: number;
  failed: number;
  categories_created: number;
  errors: ImportRowError[];
}

export interface CategoryTotal {
  category_id: string | null;
  name: string;
  color: string;
  amount: number;
  share_pct: number;
}

export interface MonthPoint {
  year: number;
  month: number;
  income: number;
  expense: number;
}

export interface MonthlyReport {
  year: number;
  month: number;
  income_total: number;
  expense_total: number;
  savings: number;
  budget_amount: number;
  remaining: number;
  utilization_pct: number;
  alert_threshold_pct: number;
  status: BudgetStatus;
  by_category: CategoryTotal[];
}

export interface Dashboard {
  year: number;
  month: number;
  budget_amount: number;
  income_total: number;
  expense_total: number;
  remaining: number;
  utilization_pct: number;
  alert_threshold_pct: number;
  status: BudgetStatus;
  by_category: CategoryTotal[];
  trend: MonthPoint[];
  recent_expenses: Transaction[];
}

export interface TransactionFilters {
  year?: number;
  month?: number;
  category_id?: string;
  q?: string;
  page?: number;
  page_size?: number;
}
