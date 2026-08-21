import { useEffect, useRef } from 'react';
import './ConfirmDialog.css';

export default function ConfirmDialog({
  title = 'Подтверждение',
  message,
  confirmLabel = 'Удалить',
  cancelLabel = 'Отмена',
  danger = true,
  busy = false,
  onConfirm,
  onCancel,
}) {
  const confirmRef = useRef(null);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && !busy) {
        e.stopPropagation();
        onCancel();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [busy, onCancel]);

  useEffect(() => {
    confirmRef.current?.focus();
  }, []);

  return (
    <div
      className="confirm-overlay"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !busy) onCancel();
      }}
    >
      <div
        className="confirm-modal"
        role="alertdialog"
        aria-modal="true"
        aria-label={title}
      >
        <h3 className="confirm-title">{title}</h3>
        <p className="confirm-message">{message}</p>
        <div className="confirm-actions">
          <button
            type="button"
            className="confirm-cancel"
            onClick={onCancel}
            disabled={busy}
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            ref={confirmRef}
            className={`confirm-ok ${danger ? 'danger' : ''}`}
            onClick={onConfirm}
            disabled={busy}
          >
            {busy ? 'Удаление…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
