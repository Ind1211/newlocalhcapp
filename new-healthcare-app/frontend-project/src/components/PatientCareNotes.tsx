import { useState } from 'react';
import { useCreateCareNote, useDeleteCareNote, usePatientCareNotes } from '../hooks/useApi';

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

export function PatientCareNotes({ patientId }: { patientId: string }) {
  const notes = usePatientCareNotes(patientId);
  const createNote = useCreateCareNote(patientId);
  const deleteNote = useDeleteCareNote(patientId);
  const [content, setContent] = useState('');

  const handleSubmit = () => {
    if (!content.trim()) return;
    createNote.mutate(content.trim(), { onSuccess: () => setContent('') });
  };

  return (
    <div className="field-group" style={{ marginBottom: 26 }}>
      <div className="section-label">Care Notes</div>

      <div style={{ marginBottom: 16 }}>
        <textarea
          className="field-input"
          style={{ width: '100%', maxWidth: 'none', minHeight: 70, fontFamily: 'var(--font-display)' }}
          placeholder="Add a note…"
          value={content}
          onChange={(e) => setContent(e.target.value)}
        />
        {createNote.isError && (
          <div style={{ fontSize: 12, color: 'var(--critical)', marginTop: 6 }}>{(createNote.error as Error).message}</div>
        )}
        <button
          className="btn btn-primary"
          style={{ marginTop: 8 }}
          disabled={!content.trim() || createNote.isPending}
          onClick={handleSubmit}
        >
          {createNote.isPending ? 'Adding…' : 'Add Note'}
        </button>
      </div>

      {notes.isLoading && <div style={{ fontSize: 13, color: 'var(--ink-soft)' }}><span className="spinner" />Loading…</div>}
      {notes.data && notes.data.length === 0 && (
        <p style={{ fontSize: 13, color: 'var(--ink-soft)', margin: 0 }}>No notes yet.</p>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {notes.data?.map((note) => (
          <div key={note.id} style={{ padding: '10px 0', borderTop: '1px solid var(--line)' }}>
            <div style={{ fontSize: 13.5 }}>{note.content}</div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 6 }}>
              <div style={{ fontSize: 11.5, color: 'var(--ink-soft)' }}>
                {note.author?.name ?? 'Unknown'} · {formatDateTime(note.created_at)}
              </div>
              <button
                className="btn"
                style={{ fontSize: 10.5, padding: '2px 8px' }}
                disabled={deleteNote.isPending}
                onClick={() => deleteNote.mutate(note.id)}
              >
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
