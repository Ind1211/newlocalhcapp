import { useState } from 'react';
import { FieldRenderer } from './FieldRenderer';
import type { FieldDef, FieldOption } from '../types';

interface PreviewField {
  id: string;
  name: string; // set to the stable local id, not the label-derived slug — the slug
  // can change on every keystroke while editing a label, which would desync echoed
  // values and show_only_if checks mid-edit. The id never changes.
  label: string;
  fieldDef: FieldDef;
  showOnlyIfFieldId?: string;
  showOnlyIfValue?: string;
}

function parseOptionsCsv(csv: string): FieldOption[] {
  return csv
    .split(',')
    .map((o) => o.trim())
    .filter(Boolean)
    .map((label) => ({ value: label, label }));
}

// Mirrors formatEchoValue() exactly: checkboxgroup joins matched labels, scale
// defaults to "5 (default, not yet moved)" rather than "No response yet" since the
// slider itself always shows 5 whether or not it's been touched, pill/select
// resolve to the matching option's label rather than its raw value.
function formatEchoValue(field: PreviewField, value: string | string[] | undefined): { display: string; empty: boolean } {
  if (field.fieldDef.type === 'checkboxgroup') {
    if (!Array.isArray(value) || value.length === 0) return { display: 'No response yet', empty: true };
    const opts = field.fieldDef.options as FieldOption[] | undefined;
    const labels = value.map((v) => opts?.find((o) => o.value === v)?.label ?? v);
    return { display: labels.join(', '), empty: false };
  }
  if (value === undefined || value === '') {
    if (field.fieldDef.type === 'scale') return { display: '5 (default, not yet moved)', empty: false };
    return { display: 'No response yet', empty: true };
  }
  if (field.fieldDef.type === 'pill' || field.fieldDef.type === 'select') {
    const opts = field.fieldDef.options as FieldOption[] | undefined;
    const match = opts?.find((o) => o.value === value);
    return { display: match?.label ?? String(value), empty: false };
  }
  return { display: String(value), empty: false };
}

export function BuilderPreview({
  title,
  blurb,
  sections,
}: {
  title: string;
  blurb: string;
  sections: { title: string; fields: { id: string; label: string; type: FieldDef['type']; optionsCsv: string; showOnlyIfFieldId: string; showOnlyIfValue: string }[] }[];
}) {
  const [previewAnswers, setPreviewAnswers] = useState<Record<string, string | string[]>>({});

  // Looked up once so isVisible can tell whether a condition's parent is a
  // checkboxgroup (an includes check) or a single-value field (an equals check) —
  // the same automatic determination used at save time, so the preview matches
  // exactly what will actually be evaluated once saved.
  const fieldTypeById = new Map<string, FieldDef['type']>();
  sections.forEach((s) => s.fields.forEach((f) => fieldTypeById.set(f.id, f.type)));

  const toPreviewField = (f: { id: string; label: string; type: FieldDef['type']; optionsCsv: string; showOnlyIfFieldId: string; showOnlyIfValue: string }): PreviewField => ({
    id: f.id,
    name: f.id,
    label: f.label,
    fieldDef: {
      name: f.id,
      label: f.label || 'Untitled question',
      type: f.type,
      options: ['pill', 'checkboxgroup', 'select'].includes(f.type) ? parseOptionsCsv(f.optionsCsv) : undefined,
    },
    showOnlyIfFieldId: f.showOnlyIfFieldId,
    showOnlyIfValue: f.showOnlyIfValue,
  });

  const isVisible = (field: PreviewField): boolean => {
    if (!field.showOnlyIfFieldId) return true;
    const parentVal = previewAnswers[field.showOnlyIfFieldId];
    // Same fix as DynamicForm's isVisible: show by default until the parent
    // question actually has an answer, rather than hiding prematurely.
    if (parentVal === undefined) return true;
    if (fieldTypeById.get(field.showOnlyIfFieldId) === 'checkboxgroup') {
      return Array.isArray(parentVal) && parentVal.includes(field.showOnlyIfValue ?? '');
    }
    return parentVal === field.showOnlyIfValue;
  };

  const set = (fieldId: string, value: string | string[] | undefined) =>
    setPreviewAnswers((a) => ({ ...a, [fieldId]: value ?? '' }));

  const hasAnyFields = sections.some((s) => s.fields.length > 0);

  return (
    <div style={{ position: 'sticky', top: 20 }}>
      <div
        style={{
          fontFamily: "'Inter', sans-serif",
          fontSize: 11.5,
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          color: 'var(--ink-soft)',
          marginBottom: 10,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <span>Live preview</span>
        <span
          style={{
            fontSize: 10.5,
            padding: '2px 8px',
            borderRadius: 10,
            background: 'var(--line-soft)',
            color: 'var(--ink-soft)',
            textTransform: 'none',
            letterSpacing: 0,
          }}
        >
          Member view
        </span>
      </div>

      <div className="card">
        <h3 style={{ fontSize: 16, marginBottom: 4, marginTop: 0 }}>{title || 'Untitled assessment'}</h3>
        {blurb && <div style={{ fontSize: 13, color: 'var(--ink-soft)', marginBottom: 16 }}>{blurb}</div>}

        {!hasAnyFields && (
          <div style={{ fontSize: 13, color: 'var(--ink-soft)' }}>Add a question to see it rendered here.</div>
        )}

        {sections.map((section, si) => {
          const visibleFields = section.fields.map(toPreviewField).filter(isVisible);
          if (visibleFields.length === 0) return null;
          return (
            <div key={si}>
              {sections.length > 1 && (
                <div
                  style={{
                    fontFamily: "'Inter', sans-serif",
                    fontSize: 11,
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    color: 'var(--ink-soft)',
                    marginTop: si === 0 ? 0 : 22,
                    marginBottom: 8,
                  }}
                >
                  {section.title}
                </div>
              )}
              {visibleFields.map((field) => (
                <PreviewFieldRow key={field.id} field={field} value={previewAnswers[field.id]} onChange={(v) => set(field.id, v)} />
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function PreviewFieldRow({
  field,
  value,
  onChange,
}: {
  field: PreviewField;
  value: string | string[] | undefined;
  onChange: (v: string | string[] | undefined) => void;
}) {
  const { display, empty } = formatEchoValue(field, value);
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 6 }}>{field.label || 'Untitled question'}</div>
      <FieldRenderer field={field.fieldDef} value={value} onChange={onChange} />
      <div style={{ fontSize: 12, color: empty ? 'var(--ink-soft)' : 'var(--accent)', marginTop: 6, fontStyle: empty ? 'italic' : 'normal' }}>
        Captured response: <strong>{display}</strong>
      </div>
    </div>
  );
}
