export interface WalletBalance {
  account_id: string;
  currency: string;
  amount: string;
  amount_major?: string;
  reserve_floor_major?: string;
  amount_cents: number;
  reserve_floor: string;
  reserve_floor_cents: number;
  headroom_major: string;
}

export interface SupplierObligation {
  obligation_id: string;
  supplier_name: string;
  invoice_ref: string;
  currency: string;
  amount: string;
  rail: string;
  rail_fee: string;
  summary: string;
  plan_action: 'FUND_NOW' | 'CONVERT_FX' | 'DEFER' | 'ESCALATE' | 'SETTLED';
  plan_rationale: string;
  approval_state: 'VALID' | 'INVALIDATED' | 'PAID' | 'NOT_APPROVED';
  approval_sha256: string | null;
  action_reason: string;
  receipt?: Record<string, unknown> | null;
}

export interface CompletenessFinding {
  rule_id: string;
  severity: 'BLOCKER' | 'WARNING';
  subject_id: string;
  message: string;
}

export interface VisaMandateState {
  card_id: string;
  obligation_id: string;
  supplier_name: string;
  limit: string;
  allowed_mcc: string;
  single_use: boolean;
  status: string;
  card_last4: string;
  last_verdict: string | null;
  last_reason: string | null;
  rebate_earned: string;
}

export interface IncidentState {
  incident_id: string;
  obligation_id: string;
  original_transfer_id: string;
  original_request_id: string;
  amount: string;
  rail: string;
  status: string;
  failure_type: string | null;
  replacement_transfer_id: string | null;
  replacement_request_id: string | null;
  swift_fees_budgeted: string;
}

export interface MetalAgentRow {
  agent_id: string;
  weight_percent: number;
  allowance: string;
  price_per_call: string;
  max_price_per_call_cents: number | null;
  call_cap: number;
  calls_used: number;
  spent: string;
}

export interface SessionInfo {
  session_id: string;
  tenant_id: string;
  user_id: string;
  email: string;
  display_name: string;
  role: 'READER' | 'EVALUATOR' | 'APPROVER' | 'WRITER' | 'ADMIN';
  csrf_token: string;
  authenticated: boolean;
  separation_of_duties: boolean;
  is_live_tenant: boolean;
  permissions: ReadonlyArray<string>;
}

export interface DepositHistoryRow {
  deposit_id: string;
  event_id: string;
  account_id: string;
  currency: string;
  amount: string;
  amount_major: string;
  payer_name: string;
  reference: string;
  recorded_at: string;
  invalidated: ReadonlyArray<string>;
  still_valid: ReadonlyArray<string>;
}

export interface FxQuoteRow {
  quote_id: string;
  from_currency: string;
  to_currency: string;
  sell_amount: string;
  sell_amount_major: string;
  buy_amount_major: string;
  rate_numerator: number;
  rate_denominator: number;
  expires_at: string;
  expired: boolean;
}

export interface FxConversionRow {
  conversion_id: string;
  quote_id: string;
  from_currency: string;
  to_currency: string;
  sold_major: string;
  bought_major: string;
  executed_at: string;
  invalidated: ReadonlyArray<string>;
}

export interface ReconciliationReport {
  tenant_id: string;
  reconciled_at: string;
  executions_count: number;
  transfers_recorded: number;
  deposits_recorded: number;
  fx_conversions_recorded: number;
  unmatched_executions: ReadonlyArray<string>;
  missing_transfer_ids: ReadonlyArray<string>;
  ledger_findings: ReadonlyArray<string>;
  execution_integrity_ok: boolean;
}

export interface TreasurySnapshot {
  mode?: string;
  tenant_id?: string;
  is_live_tenant?: boolean;
  session?: SessionInfo;
  forecast?: {
    confidence_pct: number;
    reason: string;
    autonomous_limit_major: string;
    contradicted_by_email: boolean;
  };
  fx_rates?: {
    source: string;
    as_of_date: string;
    eur_usd: string;
    eur_gbp: string;
    gbp_usd: string;
  };
  fx_quotes?: ReadonlyArray<FxQuoteRow>;
  fx_conversions?: ReadonlyArray<FxConversionRow>;
  deposit_history?: ReadonlyArray<DepositHistoryRow>;
  integrations?: Record<string, Record<string, unknown>>;
  reconciliation?: ReconciliationReport;
  last_ai_inspection?: Record<string, unknown> | null;
  last_dispute_report?: Record<string, unknown> | null;
  balances: ReadonlyArray<WalletBalance>;
  obligations: ReadonlyArray<SupplierObligation>;
  findings: ReadonlyArray<CompletenessFinding>;
  visa_mandate?: VisaMandateState;
  incident?: IncidentState;
  metal_agents?: ReadonlyArray<MetalAgentRow>;
}
