import { useRef, useState } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { BuilderPreview } from './BuilderPreview';
import {
  normalizeUploadTemplate,
  validateUploadTemplate,
  type NormalizedField,
  type NormalizedTemplate,
} from '../lib/templateUpload';

const SAMPLE_TEMPLATE = {
  name: 'Weekly Symptom Check-in',
  description: 'A short weekly check on common symptoms.',
  interpretationPrompt: 'Flag as needing follow-up if fatigue or swelling is reported as moderate or severe.',
  questions: [
    { id: 'fatigue', label: 'Fatigue level this week', type: 'radio', options: ['None', 'Mild', 'Moderate', 'Severe'] },
    { id: 'swelling', label: 'Any swelling in legs or ankles?', type: 'radio', options: ['None', 'Mild', 'Moderate', 'Severe'] },
    { id: 'detail', label: 'Anything else to note?', type: 'textarea', showIf: { id: 'swelling', equals: 'Severe' } },
  ],
};

function groupBySection(template: NormalizedTemplate): { title: string; fields: NormalizedField[] }[] {
  return template.sections.map((s) => ({
    title: s.title,
    fields: template.fields.filter((f) => f.section === s.key),
  }));
}

export function TemplateUpload({ onBack, onSaved }: { onBack: () => void; onSaved: (key: string) => void }) {
  const { user } = useAuth0();
  const creatorIdentity = user?.email ?? user?.name ?? user?.sub ?? 'Unknown user';

  const [rawText, setRawText] = useState('');
  const [showPaste, setShowPaste] = useState(false);
  const [status, setStatus] = useState<{ ok: boolean; messages: string[] } | null>(null);
  const [draft, setDraft] = useState<NormalizedTemplate | null>(null);
  const [interpretationPrompt, setInterpretationPrompt] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  const saveMutation = useMutation({
    mutationFn: (payload: unknown) => api.post<{ key: string }>('/api/assessments/custom', payload),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['assessments'] });
      onSaved(response.key);
    },
  });

  const processString = (str: string) => {
    let obj: unknown;
    try {
      obj = JSON.parse(str);
    } catch (e) {
      setStatus({ ok: false, messages: [`Invalid JSON: ${(e as Error).message}`] });
      setDraft(null);
      return;
    }
    const errors = validateUploadTemplate(obj);
    if (errors.length) {
      setStatus({ ok: false, messages: errors });
      setDraft(null);
      return;
    }
    const normalized = normalizeUploadTemplate(obj as Parameters<typeof normalizeUploadTemplate>[0]);
    setDraft(normalized);
    setInterpretationPrompt(normalized.interpretationPrompt);
    setStatus({ ok: true, messages: [`Loaded "${normalized.title}" — ${normalized.fields.length} question${normalized.fields.length === 1 ? '' : 's'} found.`] });
  };

  const handleFile = (file: File) => {
    const reader = new FileReader();
    reader.onload = () => processString(String(reader.result));
    reader.readAsText(file);
  };

  const handleSave = () => {
    if (!draft) return;
    saveMutation.mutate({
      title: draft.title,
      blurb: draft.blurb || null,
      sections: groupBySection(draft).map((s) => ({
        title: s.title,
        fields: s.fields.map((f) => ({
          name: f.name,
          label: f.label,
          type: f.type,
          options: f.options ?? null,
          unit: null,
          placeholder: null,
          required: f.required,
          show_only_if: f.show_only_if ?? null,
        })),
      })),
      interpretation_prompt: interpretationPrompt,
      created_by: creatorIdentity,
    });
  };

  return (
    <div>
      <a className="back-link" onClick={onBack}>
        ← Back
      </a>
      <h1 style={{ margin: '16px 0 4px' }}>Upload or paste a template</h1>
      <p style={{ color: 'var(--ink-soft)', fontSize: 13.5, marginTop: 0, marginBottom: 20 }}>
        Drop in JSON from another system, a colleague, or written by hand — we'll validate,
        normalize, and preview it before saving. It will appear under "Custom" in every case.
      </p>

      <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="field-group">
            <div className="field-row">
              <div className="field-label">Created by</div>
              <span style={{ fontFamily: "'Inter', sans-serif", fontSize: 13 }}>{creatorIdentity}</span>
            </div>
          </div>

          <div className="field-group">
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                const file = e.dataTransfer.files?.[0];
                if (file) handleFile(file);
              }}
              onClick={() => fileInputRef.current?.click()}
              style={{
                border: '2px dashed var(--line)', borderRadius: 10, padding: 24, textAlign: 'center', cursor: 'pointer',
              }}
            >
              <div style={{ fontSize: 14, fontWeight: 600 }}>Drag and drop a .json template file here</div>
              <div style={{ fontSize: 12.5, color: 'var(--ink-soft)', marginTop: 4 }}>
                or <span style={{ color: 'var(--accent)', fontWeight: 600, textDecoration: 'underline' }}>click to browse</span>
              </div>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".json,application/json"
              style={{ display: 'none' }}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleFile(file);
              }}
            />

            <button className="btn" style={{ marginTop: 14 }} onClick={() => setShowPaste((s) => !s)}>
              {showPaste ? 'Hide paste area' : 'Paste JSON instead'}
            </button>
            {showPaste && (
              <div style={{ marginTop: 12 }}>
                <textarea
                  className="field-input"
                  style={{ width: '100%', minHeight: 140, textAlign: 'left', fontFamily: "'Inter', sans-serif", fontSize: 12.5 }}
                  placeholder='{ "name": "...", "questions": [...] }'
                  value={rawText}
                  onChange={(e) => setRawText(e.target.value)}
                />
                <button className="btn btn-primary" style={{ marginTop: 10 }} onClick={() => processString(rawText)}>
                  Parse JSON
                </button>
              </div>
            )}

            <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
              <button className="btn" onClick={() => processString(JSON.stringify(SAMPLE_TEMPLATE))}>
                Load sample template
              </button>
              <button
                className="btn"
                onClick={() => {
                  const blob = new Blob([JSON.stringify(SAMPLE_TEMPLATE, null, 2)], { type: 'application/json' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = 'sample-assessment-template.json';
                  a.click();
                  URL.revokeObjectURL(url);
                }}
              >
                Download sample .json
              </button>
            </div>
          </div>

          {status && (
            <div className={`result-card ${status.ok ? 'good' : 'critical'}`} style={{ marginTop: 4, marginBottom: 16 }}>
              {status.messages.length > 1 ? (
                <>
                  <div className="result-headline">Template could not be loaded:</div>
                  <ul style={{ margin: '6px 0 0', paddingLeft: 18, fontSize: 13 }}>
                    {status.messages.map((m, i) => (
                      <li key={i}>{m}</li>
                    ))}
                  </ul>
                </>
              ) : (
                <div className="result-headline">{status.messages[0]}</div>
              )}
            </div>
          )}

          {draft && (
            <div className="field-group">
              <div className="field-label" style={{ marginBottom: 8 }}>
                Interpretation instructions
              </div>
              <textarea
                className="field-input"
                style={{ width: '100%', maxWidth: 'none', minHeight: 100, textAlign: 'left' }}
                placeholder="Describe how to interpret the answers..."
                value={interpretationPrompt}
                onChange={(e) => setInterpretationPrompt(e.target.value)}
              />
              <p style={{ fontSize: 12, color: 'var(--ink-soft)', marginTop: 6 }}>
                {draft.interpretationPrompt
                  ? 'Loaded from the template\'s own "interpretationPrompt" field — edit if needed.'
                  : "This template didn't include interpretation instructions — add them before saving."}
              </p>

              {saveMutation.isError && (
                <div className="result-card critical" style={{ marginTop: 12 }}>
                  <div className="result-headline">Could not save: {(saveMutation.error as Error).message}</div>
                </div>
              )}

              <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                <button className="btn" onClick={onBack}>
                  Cancel
                </button>
                <button
                  className="btn btn-primary"
                  disabled={!interpretationPrompt.trim() || saveMutation.isPending}
                  onClick={handleSave}
                >
                  {saveMutation.isPending ? 'Saving…' : 'Save assessment'}
                </button>
              </div>
            </div>
          )}
        </div>

        <div style={{ flex: 1, minWidth: 320 }}>
          {draft ? (
            <BuilderPreview
              title={draft.title}
              blurb={draft.blurb}
              sections={groupBySection(draft).map((s) => ({
                title: s.title,
                fields: s.fields.map((f) => ({
                  id: f.name,
                  label: f.label,
                  type: f.type,
                  optionsCsv: (f.options ?? []).map((o) => o.label).join(', '),
                  showOnlyIfFieldId: f.show_only_if?.field ?? '',
                  showOnlyIfValue: f.show_only_if?.equals ?? '',
                })),
              }))}
            />
          ) : (
            <div className="field-group">
              <div style={{ fontSize: 13, color: 'var(--ink-soft)' }}>Upload a JSON template to see it rendered here.</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
