import { useEffect, useRef, useState } from 'react';
import { useCreateVoiceNote, usePatientDocuments } from '../hooks/useApi';
import { EditVoiceNoteModal } from './EditVoiceNoteModal';
import { ViewTextModal } from './ViewTextModal';

// Web Speech API isn't in TypeScript's built-in DOM types, and support is
// real but inconsistent across browsers (solid in Chrome/Edge, weak or
// missing in Safari/Firefox) — this is checked explicitly rather than assumed,
// so unsupported browsers get a clear message instead of a silent, confusing failure.
type SpeechRecognitionResultLike = { transcript: string };
interface SpeechRecognitionLike extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  onresult: ((event: { resultIndex: number; results: ArrayLike<ArrayLike<SpeechRecognitionResultLike>> }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
}

function getSpeechRecognition(): (new () => SpeechRecognitionLike) | null {
  const w = window as unknown as {
    SpeechRecognition?: new () => SpeechRecognitionLike;
    webkitSpeechRecognition?: new () => SpeechRecognitionLike;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

export function PatientVoiceNotes({ patientId }: { patientId: string }) {
  const documents = usePatientDocuments(patientId);
  const createVoiceNote = useCreateVoiceNote(patientId);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  const [isRecording, setIsRecording] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [isSupported, setIsSupported] = useState(true);
  const [micError, setMicError] = useState<string | null>(null);
  const [viewingText, setViewingText] = useState<{ id: string; filename: string } | null>(null);
  const [editingNote, setEditingNote] = useState<{ id: string; filename: string } | null>(null);

  useEffect(() => {
    setIsSupported(getSpeechRecognition() !== null);
  }, []);

  const startRecording = () => {
    const SpeechRecognitionCtor = getSpeechRecognition();
    if (!SpeechRecognitionCtor) {
      setIsSupported(false);
      return;
    }
    setMicError(null);
    const recognition = new SpeechRecognitionCtor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    // Rebuilds the full transcript from scratch on every event using the
    // browser's own resultIndex — this is how the Web Speech API is actually
    // meant to be consumed (it re-sends prior results alongside new ones), not
    // something to naively append to, which would duplicate text on every event.
    recognition.onresult = (event) => {
      let fullText = '';
      for (let i = 0; i < event.results.length; i++) {
        fullText += event.results[i][0].transcript;
      }
      setTranscript(fullText);
    };

    recognition.onerror = (event) => {
      if (event.error === 'not-allowed' || event.error === 'permission-denied') {
        setMicError('Microphone access was denied — allow microphone access in your browser to dictate a note.');
      } else if (event.error === 'no-speech') {
        // Not a real error worth surfacing — just means a pause, recognition keeps listening.
      } else {
        setMicError(`Dictation stopped unexpectedly (${event.error}). You can still save what was captured, or try again.`);
      }
    };

    recognition.onend = () => setIsRecording(false);

    recognitionRef.current = recognition;
    setTranscript('');
    setIsRecording(true);
    recognition.start();
  };

  const stopRecording = () => {
    recognitionRef.current?.stop();
    setIsRecording(false);
  };

  const discardTranscript = () => {
    setTranscript('');
    setMicError(null);
  };

  const saveNote = () => {
    if (!transcript.trim()) return;
    createVoiceNote.mutate(transcript.trim(), {
      onSuccess: () => setTranscript(''),
    });
  };

  const voiceNotes = (documents.data ?? []).filter((d) => d.source === 'voice_note');

  return (
    <div className="field-group" style={{ marginBottom: 26 }}>
      <div className="section-label">Voice Notes</div>
      <p style={{ fontSize: 12.5, color: 'var(--ink-soft)', marginTop: 0, marginBottom: 14 }}>
        Dictate patient information directly — the transcript is saved as text and used to help
        fill assessments and generate the integrated care plan, the same way an uploaded document is.
      </p>

      {!isSupported && (
        <div className="result-card critical" style={{ marginBottom: 14 }}>
          <div className="result-headline">Voice dictation isn't supported in this browser.</div>
          <p style={{ fontSize: 12.5, margin: '4px 0 0' }}>Try Chrome or Edge, or type the note into a care note instead.</p>
        </div>
      )}

      {isSupported && (
        <div style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 10 }}>
            {!isRecording ? (
              <button className="btn btn-primary" onClick={startRecording}>🎙 Start Dictating</button>
            ) : (
              <button className="btn" style={{ background: 'var(--critical)', color: '#fff', borderColor: 'var(--critical)' }} onClick={stopRecording}>
                ⏹ Stop
              </button>
            )}
            {isRecording && (
              <span style={{ fontSize: 12.5, color: 'var(--ink-soft)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--critical)', display: 'inline-block' }} />
                Listening…
              </span>
            )}
          </div>

          {micError && (
            <div className="result-card critical" style={{ marginBottom: 10 }}>
              <div className="result-headline" style={{ fontSize: 12.5 }}>{micError}</div>
            </div>
          )}

          {(transcript || isRecording) && (
            <div>
              <textarea
                className="field-input"
                style={{ width: '100%', minHeight: 120, fontFamily: 'inherit', resize: 'vertical' }}
                value={transcript}
                onChange={(e) => setTranscript(e.target.value)}
                placeholder="Dictated text will appear here as you speak — you can edit it before saving."
                disabled={isRecording}
              />
              <p style={{ fontSize: 11.5, color: 'var(--ink-soft)', margin: '4px 0 10px' }}>
                Speech recognition isn't perfect — review and correct the text above before saving, especially medication names or numbers.
              </p>
              {!isRecording && transcript.trim() && (
                <div style={{ display: 'flex', gap: 8 }}>
                  <button className="btn" onClick={discardTranscript}>Discard</button>
                  <button className="btn btn-primary" disabled={createVoiceNote.isPending} onClick={saveNote}>
                    {createVoiceNote.isPending ? 'Saving…' : 'Save Voice Note'}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {createVoiceNote.isError && (
        <div className="result-card critical" style={{ marginBottom: 14 }}>
          <div className="result-headline">{(createVoiceNote.error as Error).message}</div>
        </div>
      )}

      <div className="section-label" style={{ fontSize: 11, marginBottom: 6 }}>Past Voice Notes</div>
      {documents.isLoading && <div style={{ fontSize: 13, color: 'var(--ink-soft)' }}><span className="spinner" />Loading…</div>}
      {voiceNotes.length === 0 && !documents.isLoading && (
        <p style={{ fontSize: 13, color: 'var(--ink-soft)', margin: 0 }}>No voice notes recorded yet.</p>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {voiceNotes.map((note) => (
          <div key={note.id} style={{ padding: '10px 0', borderTop: '1px solid var(--line)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ fontSize: 11.5, color: 'var(--ink-soft)' }}>
              <div>{note.uploaded_by ?? 'Unknown'}</div>
              <div>{formatDateTime(note.uploaded_at)}</div>
            </div>
            <button className="btn" style={{ fontSize: 12 }} onClick={() => setViewingText({ id: note.id, filename: note.filename })}>
              View Text
            </button>
            <button className="btn" style={{ fontSize: 12, marginLeft: 6 }} onClick={() => setEditingNote({ id: note.id, filename: note.filename })}>
              Edit
            </button>
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

      {editingNote && (
        <EditVoiceNoteModal
          patientId={patientId}
          documentId={editingNote.id}
          filename={editingNote.filename}
          onClose={() => setEditingNote(null)}
        />
      )}
    </div>
  );
}
