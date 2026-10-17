import { useDocumentDetail } from '../hooks/useApi';

export function ViewTextModal({ patientId, documentId, filename, onClose }: { patientId: string; documentId: string; filename: string; onClose: () => void }) {
  const detail = useDocumentDetail(patientId, documentId);
  return (
    <div
      style={{ position: 'fixed', inset: 0, background: 'rgba(15,24,26,.45)', zIndex: 55, display: 'flex', alignItems: 'flex-start', justifyContent: 'center', padding: '40px 20px', overflowY: 'auto' }}
      onClick={onClose}
    >
      <div style={{ background: 'var(--surface)', borderRadius: 14, width: '100%', maxWidth: 640, border: '1px solid var(--line)', maxHeight: '80vh', display: 'flex', flexDirection: 'column' }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px', borderBottom: '1px solid var(--line)' }}>
          <h3 style={{ margin: 0, fontSize: 15 }}>{filename}</h3>
          <button className="btn" style={{ padding: '4px 8px' }} onClick={onClose}>✕</button>
        </div>
        <div style={{ padding: 20, overflowY: 'auto', whiteSpace: 'pre-wrap', fontSize: 13, lineHeight: 1.6, fontFamily: "'Inter', sans-serif" }}>
          {detail.isLoading && <span><span className="spinner" />Loading…</span>}
          {detail.data?.extracted_text || (detail.data && !detail.isLoading ? 'No text available.' : null)}
        </div>
      </div>
    </div>
  );
}
