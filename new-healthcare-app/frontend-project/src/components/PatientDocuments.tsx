import { useRef, useState } from 'react';
import { useDeleteDocument, usePatientDocuments, useRetryExtraction, useUploadDocument } from '../hooks/useApi';
import { ViewTextModal } from './ViewTextModal';
import { api } from '../api/client';
import type { PatientDocument } from '../types';

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}


function ExtractionTag({ doc }: { doc: PatientDocument }) {
  if (doc.extraction_status === 'pending') return <span className="tag tag-caution">Processing…</span>;
  if (doc.extraction_status === 'ok') return <span className="tag tag-good">Text extracted</span>;
  return <span className="tag tag-critical">Extraction failed</span>;
}

export function PatientDocuments({ patientId }: { patientId: string }) {
  const documents = usePatientDocuments(patientId);
  const upload = useUploadDocument(patientId);
  const deleteDoc = useDeleteDocument(patientId);
  const retryExtraction = useRetryExtraction(patientId);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [viewingText, setViewingText] = useState<{ id: string; filename: string } | null>(null);

  const handleFile = (file: File) => {
    upload.mutate(file, { onSuccess: () => setDownloadError(null) });
  };

  const handleDownload = async (doc: PatientDocument) => {
    setDownloadError(null);
    try {
      const blob = await api.getBlob(`/api/patients/${patientId}/documents/${doc.id}/file`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = doc.filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setDownloadError((e as Error).message);
    }
  };

  return (
    <div className="field-group" style={{ marginBottom: 26 }}>
      <div className="section-label">Documents</div>
      <p style={{ fontSize: 12.5, color: 'var(--ink-soft)', marginTop: 0, marginBottom: 16 }}>
        Referral letters, lab reports, discharge summaries — PDF, DOCX, or plain text. Text is
        extracted automatically so it can be used to help fill out assessments later.
      </p>

      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          const file = e.dataTransfer.files?.[0];
          if (file) handleFile(file);
        }}
        onClick={() => fileInputRef.current?.click()}
        style={{
          border: '2px dashed var(--line)', borderRadius: 10, padding: 20, textAlign: 'center',
          cursor: 'pointer', marginBottom: 16,
        }}
      >
        <div style={{ fontSize: 13.5, fontWeight: 600 }}>
          {upload.isPending ? <><span className="spinner" />Uploading…</> : 'Drag and drop a document here'}
        </div>
        {!upload.isPending && (
          <div style={{ fontSize: 12, color: 'var(--ink-soft)', marginTop: 4 }}>
            or <span style={{ color: 'var(--accent)', fontWeight: 600, textDecoration: 'underline' }}>click to browse</span>
          </div>
        )}
      </div>
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
        style={{ display: 'none' }}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
          e.target.value = '';
        }}
      />

      {upload.isError && (
        <div className="result-card critical" style={{ marginBottom: 16 }}>
          <div className="result-headline">{(upload.error as Error).message}</div>
        </div>
      )}
      {downloadError && (
        <div className="result-card critical" style={{ marginBottom: 16 }}>
          <div className="result-headline">Could not download: {downloadError}</div>
        </div>
      )}

      {documents.isLoading && (
        <div style={{ fontSize: 13, color: 'var(--ink-soft)' }}><span className="spinner" />Loading documents…</div>
      )}

      {documents.data && documents.data.length === 0 && (
        <p style={{ fontSize: 13, color: 'var(--ink-soft)', margin: 0 }}>No documents uploaded yet.</p>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {documents.data?.map((doc) => (
          <div
            key={doc.id}
            style={{
              display: 'flex', alignItems: 'center', gap: 12, padding: '10px 0',
              borderTop: '1px solid var(--line)',
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 600, fontSize: 13.5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {doc.source === 'voice_note' && <span title="Recorded as a voice note" style={{ marginRight: 5 }}>🎙</span>}
                {doc.filename}
              </div>
              <div style={{ fontSize: 11.5, color: 'var(--ink-soft)', marginTop: 2 }}>
                {formatSize(doc.size_bytes)} · {formatDate(doc.uploaded_at)}
              </div>
              {doc.extraction_status === 'failed' && doc.extraction_error && (
                <div style={{ fontSize: 11.5, color: 'var(--critical)', marginTop: 2 }}>{doc.extraction_error}</div>
              )}
            </div>
            <ExtractionTag doc={doc} />
            {confirmingDelete === doc.id ? (
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <button className="btn" style={{ fontSize: 12 }} onClick={() => setConfirmingDelete(null)}>Cancel</button>
                <button
                  className="btn"
                  style={{ fontSize: 12, background: 'var(--critical)', color: '#fff', borderColor: 'var(--critical)' }}
                  disabled={deleteDoc.isPending}
                  onClick={() => deleteDoc.mutate(doc.id, { onSuccess: () => setConfirmingDelete(null) })}
                >
                  {deleteDoc.isPending ? 'Deleting…' : 'Confirm'}
                </button>
              </div>
            ) : (
              <div style={{ display: 'flex', gap: 6 }}>
                {doc.extraction_status === 'ok' && (
                  <button className="btn" style={{ fontSize: 12 }} onClick={() => setViewingText({ id: doc.id, filename: doc.filename })}>View Text</button>
                )}
                {doc.extraction_status === 'failed' && (
                  <button
                    className="btn" style={{ fontSize: 12 }}
                    disabled={retryExtraction.isPending}
                    onClick={() => retryExtraction.mutate(doc.id)}
                  >
                    {retryExtraction.isPending ? 'Retrying…' : 'Retry'}
                  </button>
                )}
                <button className="btn" style={{ fontSize: 12 }} onClick={() => handleDownload(doc)}>Download</button>
                <button className="btn" style={{ fontSize: 12 }} onClick={() => setConfirmingDelete(doc.id)}>Delete</button>
              </div>
            )}
          </div>
        ))}
      </div>

      {viewingText && (
        <ViewTextModal
          patientId={patientId}
          documentId={viewingText.id}
          filename={viewingText.filename}
          onClose={() => setViewingText(null)}
        />
      )}
    </div>
  );
}
