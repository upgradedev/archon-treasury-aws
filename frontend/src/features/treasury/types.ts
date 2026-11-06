export interface WalletBalance {
  account_id: string;
  currency: string;
  amount: string;
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

export interface TreasurySnapshot {
  balances: ReadonlyArray<WalletBalance>;
  obligations: ReadonlyArray<SupplierObligation>;
  findings: ReadonlyArray<CompletenessFinding>;
  visa_mandate?: VisaMandateState;
  incident?: IncidentState;
  metal_agents?: ReadonlyArray<MetalAgentRow>;
}
