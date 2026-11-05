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

export interface TreasurySnapshot {
  balances: ReadonlyArray<WalletBalance>;
  obligations: ReadonlyArray<SupplierObligation>;
  findings: ReadonlyArray<CompletenessFinding>;
}
