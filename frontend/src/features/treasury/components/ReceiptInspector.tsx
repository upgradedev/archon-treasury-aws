import React from 'react';
import { Badge } from '../../../components/ui/Badge';

interface ReceiptInspectorProps {
  supplierName: string;
  invoiceRef: string;
  approvalSha256: string | null;
  receipt: Record<string, unknown> | null | undefined;
}

export const ReceiptInspector: React.FC<ReceiptInspectorProps> = ({
  supplierName,
  invoiceRef,
  approvalSha256,
  receipt,
}) => {
  if (!receipt) return null;
  const verified = Boolean(receipt.merkle_verified);
  const merkleRoot = String(receipt.merkle_root_sha256 ?? '');
  const spokenText = String(receipt.spoken_text ?? '');
  const brailleText = String(receipt.braille_transcript ?? '');

  return (
    <section className="list-row">
      <div className="section-heading">
        <h3>
          {supplierName} · {invoiceRef}
        </h3>
        <Badge intent={verified ? 'success' : 'critical'}>
          {verified ? 'MERKLE SEAL VERIFIED' : 'UNVERIFIED'}
        </Badge>
      </div>
      <dl className="details">
        <dt>Approval SHA-256</dt>
        <dd className="money">{approvalSha256 ?? 'N/A'}</dd>
        <dt>Merkle Root SHA-256</dt>
        <dd className="money">{merkleRoot || 'N/A'}</dd>
        {spokenText && (
          <>
            <dt>Spoken Receipt</dt>
            <dd>{spokenText}</dd>
          </>
        )}
        {brailleText && (
          <>
            <dt>Braille Transcript</dt>
            <dd className="money">{brailleText}</dd>
          </>
        )}
      </dl>
      <pre className="data-block">{JSON.stringify(receipt, null, 2)}</pre>
    </section>
  );
};
