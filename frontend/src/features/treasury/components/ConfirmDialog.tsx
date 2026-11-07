import React, { useEffect, useRef } from 'react';
import { Button } from '../../../components/ui/Button';

export interface ConfirmActionState {
  name: string;
  path: string;
  body: Record<string, unknown>;
}

interface ConfirmDialogProps {
  confirmAction: ConfirmActionState | null;
  unavailable: boolean;
  onCancel: () => void;
  onConfirm: (action: ConfirmActionState) => void;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  confirmAction,
  unavailable,
  onCancel,
  onConfirm,
}) => {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!confirmAction) return;
    previousFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;

    const timer = window.setTimeout(() => {
      const firstBtn = dialogRef.current?.querySelector<HTMLElement>('button:not([disabled])');
      firstBtn?.focus();
    }, 0);

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onCancel();
        return;
      }
      if (event.key === 'Tab' && dialogRef.current) {
        const focusables = Array.from(
          dialogRef.current.querySelectorAll<HTMLElement>(
            'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
          )
        );
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      window.clearTimeout(timer);
      document.removeEventListener('keydown', handleKeyDown);
      previousFocusRef.current?.focus();
    };
  }, [confirmAction, onCancel]);

  if (!confirmAction) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-overlay flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Confirm action"
    >
      <div
        ref={dialogRef}
        className="bg-surface border border-border rounded-md p-6 max-w-lg w-full"
      >
        <h2 className="text-lg font-medium">{confirmAction.name}</h2>
        <p className="muted my-4">
          The current service will validate this request before applying it.
        </p>
        <div className="toolbar">
          <Button onClick={onCancel}>Cancel</Button>
          <Button
            variant="primary"
            disabled={unavailable}
            onClick={() => onConfirm(confirmAction)}
          >
            Confirm
          </Button>
        </div>
      </div>
    </div>
  );
};
