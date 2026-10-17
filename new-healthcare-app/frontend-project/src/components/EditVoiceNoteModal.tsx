import { useEffect, useState } from 'react';
import { useDocumentDetail, useUpdateVoiceNote } from '../hooks/useApi';

export function EditVoiceNoteModal({
  patientId,
  documentId,
  filename,
  onClose,
}: {
  patientId: string;
  documentId: string;
  filename: string;
  onClose: () => void;
}) {
  const detail = useDocumentDetail(patientId, documentId);
  const updateVoiceNote = useUpdateVoiceNote(patientId);
  const [text, setText] = useState('');

  // Seeds the textarea once the real text has loaded — not on every render,
  // which would otherwise stomp on whatever someone's already typed.
  useEffect(() => {
    if (detail.data?.extracted_text) setText(detail.data.extracted_text);
  }, [detail.data?.extracted_text]);

  const handleSave = () => {
    if (!text.trim()) return;
    updateVoiceNote.mutate({ documentId, text: text.trim() }, { onSuccess: onClose });
  };

  return (
    <div
      style={{ position: 'fixed', inset: 0, background: 'rgba(15,24,26,.45)', zIndex: 55, display: 'flex', alignItems: 'flex-start', justifyContent: 'center', padding: '40px 20px', overflowY: 'auto' }}
      onClick={onClose}
    >
      <div style={{ background: 'var(--surface)', borderRadius: 14, width: '100%', maxWidth: 640, border: '1px solid var(--line)', maxHeight: '80vh', display: 'flex', flexDirection: 'column' }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px', borderBottom: '1px solid var(--line)' }}>
          <h3 style={{ margin: 0, fontSize: 15 }}>Edit — {filename}</h3>
          <button className="btn" style={{ padding: '4px 8px' }} onClick={onClose}>✕</button>
        </div>
        <div style={{ padding: 20, overflowY: 'auto' }}>
          {detail.isLoading ? (
            <span style={{ fontSize: 13, color: 'var(--ink-soft)' }}><span className="spinner" />Loading…</span>
          ) : (
            <textarea
              className="field-input"
              style={{ width: '100%', minHeight: 220, fontFamily: "'Inter', sans-serif", fontSize: 13, lineHeight: 1.6, resize: 'vertical' }}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          )}
          {updateVoiceNote.isError && (
            <div className="result-card critical" style={{ marginTop: 12 }}>
              <div className="result-headline" style={{ fontSize: 12.5 }}>{(updateVoiceNote.error as Error).message}</div>
            </div>
          )}
        </div>
        <div style={{ padding: '14px 20px', borderTop: '1px solid var(--line)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={!text.trim() || updateVoiceNote.isPending} onClick={handleSave}>
            {updateVoiceNote.isPending ? 'Saving…' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
}
