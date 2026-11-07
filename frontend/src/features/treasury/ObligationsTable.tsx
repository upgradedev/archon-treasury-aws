import React,{useMemo} from 'react';
import {Badge,BadgeIntent} from '../../components/ui/Badge';
import {Button} from '../../components/ui/Button';
import {Table,TableColumn} from '../../components/ui/Table';
import {SupplierObligation} from './types';
interface Props{obligations:ReadonlyArray<SupplierObligation>;onApprove:(id:string)=>void;onExecute:(id:string,sha:string|null)=>void;busy?:boolean;}
const PLAN_INTENT:Record<SupplierObligation['plan_action'],BadgeIntent>={FUND_NOW:'success',CONVERT_FX:'indigo',DEFER:'warning',ESCALATE:'critical',SETTLED:'neutral'};
const STATE_INTENT:Record<SupplierObligation['approval_state'],BadgeIntent>={VALID:'success',INVALIDATED:'critical',PAID:'indigo',NOT_APPROVED:'neutral'};
export const ObligationsTable:React.FC<Props>=({obligations,onApprove,onExecute,busy=false})=>{
 const columns=useMemo<ReadonlyArray<TableColumn<SupplierObligation>>>(()=>[
 {key:'supplier',header:'Supplier & Invoice',render:o=><div><div className="font-semibold text-foreground">{o.supplier_name}</div><div className="text-xs text-muted mt-0.5"><code className="font-mono bg-surface-2 border border-border px-1 rounded-sm">{o.obligation_id}</code> · {o.invoice_ref} · {o.summary}</div></div>},
 {key:'amount',header:'Amount & Rail',align:'right',render:o=><div><div className="font-mono tabular-nums font-bold text-foreground">{o.amount}</div><div className="text-xs text-muted mt-0.5"><span className="inline-block bg-surface-2 border border-border px-1 rounded-sm font-bold text-[11px] text-foreground">{o.rail}</span> Fee: <span className="font-mono tabular-nums">{o.rail_fee}</span></div></div>},
 {key:'plan',header:'Agent Triage Plan',render:o=><div><Badge intent={PLAN_INTENT[o.plan_action]}>{o.plan_action}</Badge><div className="text-xs text-muted mt-1">{o.plan_rationale}</div></div>},
 {key:'approval',header:'Approval & Gate Status',render:o=><div><Badge intent={STATE_INTENT[o.approval_state]}>{o.approval_state}</Badge>{o.approval_sha256&&<div className="text-xs text-muted mt-1 font-mono tabular-nums">SHA-256: {o.approval_sha256.slice(0,12)}</div>}<div className="text-xs text-muted mt-0.5">{o.action_reason}</div></div>},
 {key:'actions',header:'Actions',render:o=><div className="flex flex-col gap-1.5"><Button size="sm" variant="secondary" disabled={busy||o.approval_state==='PAID'} onClick={()=>onApprove(o.obligation_id)}>Approve</Button><Button size="sm" variant="primary" disabled={busy||o.approval_state!=='VALID'} onClick={()=>onExecute(o.obligation_id,o.approval_sha256)}>Execute</Button></div>}
 ],[onApprove,onExecute,busy]);
 return <Table ariaLabel="Supplier payouts table, scrollable" columns={columns} rows={obligations} getRowKey={o=>o.obligation_id}/>;
};
