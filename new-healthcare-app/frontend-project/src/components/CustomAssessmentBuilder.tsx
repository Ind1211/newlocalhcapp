import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth0 } from '@auth0/auth0-react';
import { api } from '../api/client';
import { LibraryPicker, type PickedQuestion } from './LibraryPicker';
import { BuilderPreview } from './BuilderPreview';

interface BuilderField {
  id: string;
  name: string;
  label: string;
  type: 'text' | 'textarea' | 'number' | 'pill' | 'checkboxgroup' | 'select' | 'scale';
  optionsCsv: string;
  required: boolean;
  showOnlyIfFieldId: string;
  showOnlyIfValue: string;
}

interface BuilderSection {
  id: string;
  title: string;
  description: string;
  fields: BuilderField[];
}

const TYPE_LABELS: Record<BuilderField['type'], string> = {
  text: 'Short text',
  textarea: 'Long text',
  number: 'Number',
  pill: 'Single choice',
  checkboxgroup: 'Multi-select',
  select: 'Dropdown',
  scale: '0–10 scale',
};

function slugify(label: string): string {
  return (
    label
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '') || 'field'
  );
}

function newField(): BuilderField {
  return {
    id: crypto.randomUUID(),
    name: '',
    label: '',
    type: 'text',
    optionsCsv: '',
    required: true,
    showOnlyIfFieldId: '',
    showOnlyIfValue: '',
  };
}

function newSection(title: string): BuilderSection {
  return { id: crypto.randomUUID(), title, description: '', fields: [] };
}

interface RawField {
  name: string;
  label: string;
  type: string;
  options?: { value: string; label: string }[] | string[] | null;
  required?: boolean;
  show_only_if?: { field: string; equals?: string; includes?: string } | null;
}
interface RawStep {
  title: string;
  fields: RawField[];
}
interface EditableAssessment {
  key: string;
  title: string;
  blurb: string | null;
  fields?: { steps: RawStep[] | null; fields: RawField[] | null } | null;
  interpretation_prompt?: string | null;
}

function reconstructSections(assessment: EditableAssessment): BuilderSection[] {
  const rawSteps: RawStep[] =
    assessment.fields?.steps ??
    (assessment.fields?.fields ? [{ title: 'Main', fields: assessment.fields.fields }] : [{ title: 'Main', fields: [] }]);

  return rawSteps.map((step) => {
    const nameToId = new Map<string, string>();
    const pendingConditions: { fieldId: string; targetName: string; value: string }[] = [];

    const fields: BuilderField[] = step.fields.map((f) => {
      const id = crypto.randomUUID();
      nameToId.set(f.name, id);
      if (f.show_only_if) {
        // equals and includes both just become "the value to match" here — which
        // one gets saved is re-derived automatically from the parent field's type
        // at save time, so there's nothing else to reconstruct.
        const matchValue = f.show_only_if.equals ?? f.show_only_if.includes ?? '';
        pendingConditions.push({ fieldId: id, targetName: f.show_only_if.field, value: matchValue });
      }
      const optionsCsv = f.options
        ? f.options.map((o) => (typeof o === 'string' ? o : o.label)).join(', ')
        : '';
      return {
        id,
        name: f.name,
        label: f.label,
        type: f.type as BuilderField['type'],
        optionsCsv,
        required: f.required !== false,
        showOnlyIfFieldId: '',
        showOnlyIfValue: '',
      };
    });

    // Second pass — now that every field in this section has a generated id, resolve
    // each show_only_if's name-reference into the matching local id.
    for (const cond of pendingConditions) {
      const field = fields.find((f) => f.id === cond.fieldId)!;
      field.showOnlyIfFieldId = nameToId.get(cond.targetName) ?? '';
      field.showOnlyIfValue = cond.value;
    }

    return { id: crypto.randomUUID(), title: step.title, description: '', fields };
  });
}

export function CustomAssessmentBuilder({
  onBack,
  onSaved,
  editingAssessment,
}: {
  onBack: () => void;
  onSaved: (key: string) => void;
  editingAssessment?: EditableAssessment;
}) {
  const { user } = useAuth0();
  // Real identity from the auth session, not a self-reported text field — a genuine
  // improvement over the original app, which explicitly could only self-report a name
  // because it had no login system at all.
  const creatorIdentity = user?.email ?? user?.name ?? user?.sub ?? 'Unknown user';
  const isEditing = !!editingAssessment;
  const [title, setTitle] = useState(editingAssessment?.title ?? '');
  const [blurb, setBlurb] = useState(editingAssessment?.blurb ?? '');
  const [sections, setSections] = useState<BuilderSection[]>(
    editingAssessment ? reconstructSections(editingAssessment) : [newSection('Main')]
  );
  const [interpretationPrompt, setInterpretationPrompt] = useState(editingAssessment?.interpretation_prompt ?? '');
  const [pickerOpenForSection, setPickerOpenForSection] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const saveMutation = useMutation({
    mutationFn: (payload: unknown) =>
      isEditing
        ? api.put<{ key: string }>(`/api/assessments/custom/${editingAssessment!.key}`, payload)
        : api.post<{ key: string }>('/api/assessments/custom', payload),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['assessments'] });
      onSaved(isEditing ? editingAssessment!.key : response.key);
    },
  });

  const updateSection = (id: string, patch: Partial<BuilderSection>) =>
    setSections((s) => s.map((sec) => (sec.id === id ? { ...sec, ...patch } : sec)));

  const addSection = () => setSections((s) => [...s, newSection(`Section ${s.length + 1}`)]);
  const removeSection = (id: string) => setSections((s) => (s.length > 1 ? s.filter((sec) => sec.id !== id) : s));

  const addField = (sectionId: string) =>
    updateSection(sectionId, { fields: [...sections.find((s) => s.id === sectionId)!.fields, newField()] });

  const addFieldsFromLibrary = (sectionId: string, picked: PickedQuestion[]) => {
    const section = sections.find((s) => s.id === sectionId)!;
    const newFields: BuilderField[] = picked.map((p) => ({
      id: crypto.randomUUID(),
      name: '',
      label: p.label,
      type: p.type,
      optionsCsv: p.optionsCsv,
      required: true,
      showOnlyIfFieldId: '',
      showOnlyIfValue: '',
    }));
    updateSection(sectionId, { fields: [...section.fields, ...newFields] });
    setPickerOpenForSection(null);
  };

  const updateField = (sectionId: string, fieldId: string, patch: Partial<BuilderField>) => {
    const section = sections.find((s) => s.id === sectionId)!;
    updateSection(sectionId, {
      fields: section.fields.map((f) => (f.id === fieldId ? { ...f, ...patch } : f)),
    });
  };

  const removeField = (sectionId: string, fieldId: string) => {
    const section = sections.find((s) => s.id === sectionId)!;
    updateSection(sectionId, { fields: section.fields.filter((f) => f.id !== fieldId) });
  };

  const moveField = (sectionId: string, fieldId: string, dir: -1 | 1) => {
    const section = sections.find((s) => s.id === sectionId)!;
    const idx = section.fields.findIndex((f) => f.id === fieldId);
    const swapIdx = idx + dir;
    if (swapIdx < 0 || swapIdx >= section.fields.length) return;
    const next = [...section.fields];
    [next[idx], next[swapIdx]] = [next[swapIdx], next[idx]];
    updateSection(sectionId, { fields: next });
  };

  // Matches the verified original BUILDER_CONDITIONAL_PARENT_TYPES (radio, dropdown,
  // checkbox, yesno) translated to this app's internal type vocabulary — pill, select,
  // and checkboxgroup are all eligible; a plain text/number/scale answer isn't a
  // meaningful thing to branch on.
  const choiceFieldsBefore = (sectionId: string, fieldId: string): BuilderField[] => {
    const section = sections.find((s) => s.id === sectionId)!;
    const idx = section.fields.findIndex((f) => f.id === fieldId);
    return section.fields.slice(0, idx).filter((f) => f.type === 'pill' || f.type === 'select' || f.type === 'checkboxgroup');
  };

  const allFieldsFilled = sections.every((s) => s.fields.every((f) => f.label.trim() !== ''));
  const canSave = title.trim() !== '' && interpretationPrompt.trim() !== '' && sections.some((s) => s.fields.length > 0) && allFieldsFilled;

  const handleSave = () => {
    const payloadSections = sections.map((s) => ({
      title: s.title,
      description: s.description || null,
      fields: s.fields.map((f) => {
        const name = f.name || slugify(f.label);
        const needsOptions = f.type === 'pill' || f.type === 'checkboxgroup' || f.type === 'select';
        const options = needsOptions
          ? f.optionsCsv
              .split(',')
              .map((o) => o.trim())
              .filter(Boolean)
              .map((o) => ({ value: slugify(o), label: o }))
          : null;
        const refField = s.fields.find((x) => x.id === f.showOnlyIfFieldId);
        // A checkboxgroup answer is always an array — checking it against a
        // single value is inherently an "includes" condition, not "equals".
        // Determined automatically from the parent's type rather than exposing
        // a separate condition-type control, since the parent's type already
        // fully determines which one is even meaningful.
        const showOnlyIf = f.showOnlyIfFieldId && refField
          ? refField.type === 'checkboxgroup'
            ? { field: refField.name || slugify(refField.label), includes: f.showOnlyIfValue }
            : { field: refField.name || slugify(refField.label), equals: f.showOnlyIfValue }
          : null;
        return {
          name,
          label: f.label,
          type: f.type,
          options,
          unit: null,
          placeholder: null,
          required: f.required,
          show_only_if: showOnlyIf,
        };
      }),
    }));

    saveMutation.mutate({
      title,
      blurb: blurb || null,
      sections: payloadSections,
      interpretation_prompt: interpretationPrompt,
      created_by: creatorIdentity,
    });
  };

  if (pickerOpenForSection) {
    return (
      <LibraryPicker
        programFilter={null}
        onAdd={(picked) => addFieldsFromLibrary(pickerOpenForSection, picked)}
        onCancel={() => setPickerOpenForSection(null)}
      />
    );
  }

  return (
    <div className="compact-assessment-builder">
      <a className="back-link" onClick={onBack}>
        ← Back
      </a>
      <h1 style={{ margin: '10px 0 4px', fontSize: 22 }}>{isEditing ? 'Edit custom assessment' : 'Build a custom assessment'}</h1>
      <p style={{ color: 'var(--ink-soft)', fontSize: 12.5, marginTop: 0, marginBottom: 14 }}>
        {isEditing
          ? 'Saving creates a new version — the previous version stays in history, and any case that already used it keeps its original answers and result.'
          : 'Define the questions, then describe in plain language how AI should interpret the answers. This is your team\'s own tool — not independently reviewed like the built-in library. It will appear under "Custom" in every case.'}
      </p>

      <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="field-group">
        <div className="field-row">
          <div className="field-label">Created by</div>
          <span style={{ fontFamily: "'Inter', sans-serif", fontSize: 13 }}>{creatorIdentity}</span>
        </div>
        <div className="field-row">
          <div className="field-label">Title</div>
          <input
            className="field-input"
            style={{ width: '100%', maxWidth: 'none', textAlign: 'left' }}
            placeholder="e.g. Kidney Care Daily check-in"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>
        <div className="field-row">
          <div className="field-label">Short description</div>
          <input
            className="field-input"
            style={{ width: '100%', maxWidth: 'none', textAlign: 'left' }}
            placeholder="One sentence describing what this checks"
            value={blurb}
            onChange={(e) => setBlurb(e.target.value)}
          />
        </div>
      </div>

      <div className="field-group" style={{ marginTop: 16 }}>
        <div className="section-label">Categories</div>
        <p style={{ fontSize: 12, color: 'var(--ink-soft)', marginTop: 0, marginBottom: 12 }}>Group questions into sections. Two or more turns this into a multi-step wizard when filled out.</p>
        {sections.map((section) => (
          <div key={section.id} style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
            <input
              className="field-input"
              style={{ width: 200, maxWidth: 'none', textAlign: 'left' }}
              value={section.title}
              onChange={(e) => updateSection(section.id, { title: e.target.value })}
            />
            <input
              className="field-input"
              style={{ flex: 1, maxWidth: 'none', textAlign: 'left' }}
              placeholder="Optional description"
              value={section.description}
              onChange={(e) => updateSection(section.id, { description: e.target.value })}
            />
            {sections.length > 1 && (
              <button className="btn" onClick={() => removeSection(section.id)} aria-label="Remove category">✕</button>
            )}
          </div>
        ))}
        <button className="btn" style={{ fontSize: 12.5, marginTop: 4 }} onClick={addSection}>+ Add category</button>
      </div>

      <div className="field-group" style={{ marginTop: 16 }}>
        <div className="section-label" style={{ marginBottom: 14 }}>Questions</div>
        {(() => {
          let globalIndex = 0;
          return sections.flatMap((section) =>
            section.fields.map((field, i) => {
              const displayNumber = ++globalIndex;
              return (
            <div key={field.id} style={{ border: '1px solid var(--line)', borderRadius: 10, padding: '10px 14px', marginBottom: 8 }}>
              <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 8 }}>
                <span
                  style={{
                    width: 22, height: 22, borderRadius: '50%', background: 'var(--accent-tint)', color: 'var(--accent)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700, flexShrink: 0,
                  }}
                >
                  {displayNumber}
                </span>
                <input
                  className="field-input"
                  style={{ flex: 1, textAlign: 'left', fontSize: 14, maxWidth: 'none' }}
                  placeholder="Question label"
                  value={field.label}
                  onChange={(e) => updateField(section.id, field.id, { label: e.target.value })}
                />
                <button className="btn" style={{ padding: '5px 8px', fontSize: 11 }} onClick={() => moveField(section.id, field.id, -1)} disabled={i === 0} title="Move up">↑</button>
                <button className="btn" style={{ padding: '5px 8px', fontSize: 11 }} onClick={() => moveField(section.id, field.id, 1)} disabled={i === section.fields.length - 1} title="Move down">↓</button>
                <button className="btn" style={{ padding: '6px 9px', fontSize: 12, color: 'var(--ink-soft)' }} onClick={() => removeField(section.id, field.id)} title="Remove question">✕</button>
              </div>

              <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                <select
                  className="field-input"
                  style={{ width: 140, textAlign: 'left', fontSize: 12.5, padding: '6px 8px', maxWidth: 'none' }}
                  value={field.type}
                  onChange={(e) => updateField(section.id, field.id, { type: e.target.value as BuilderField['type'] })}
                >
                  {Object.entries(TYPE_LABELS).map(([val, label]) => <option key={val} value={val}>{label}</option>)}
                </select>
                <select
                  className="field-input"
                  style={{ width: 180, textAlign: 'left', fontSize: 12.5, padding: '6px 8px', maxWidth: 'none' }}
                  value={section.id}
                  onChange={(e) => {
                    const targetSectionId = e.target.value;
                    if (targetSectionId === section.id) return;
                    const targetSection = sections.find((s) => s.id === targetSectionId)!;
                    updateSection(section.id, { fields: section.fields.filter((f) => f.id !== field.id) });
                    updateSection(targetSectionId, { fields: [...targetSection.fields, { ...field, showOnlyIfFieldId: '', showOnlyIfValue: '' }] });
                  }}
                  title="Category"
                >
                  {sections.map((s) => <option key={s.id} value={s.id}>{s.title || 'Untitled category'}</option>)}
                </select>

                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5, color: 'var(--ink-soft)', marginLeft: 'auto', cursor: 'pointer' }}>
                  Required
                  <span
                    onClick={() => updateField(section.id, field.id, { required: !field.required })}
                    style={{
                      width: 36, height: 20, borderRadius: 10, position: 'relative', flexShrink: 0, transition: 'background-color 0.15s ease',
                      background: field.required ? 'var(--accent)' : 'var(--line)',
                    }}
                  >
                    <span
                      style={{
                        position: 'absolute', top: 2, left: field.required ? 18 : 2, width: 16, height: 16, borderRadius: '50%',
                        background: '#fff', transition: 'left 0.15s ease', boxShadow: '0 1px 2px rgba(0,0,0,0.2)',
                      }}
                    />
                  </span>
                </label>
              </div>

              {(field.type === 'pill' || field.type === 'checkboxgroup' || field.type === 'select') && (
                <input
                  className="field-input"
                  style={{ width: '100%', maxWidth: 'none', textAlign: 'left', marginTop: 10, fontSize: 13 }}
                  placeholder="Options, comma-separated (e.g. Yes, No, Unsure)"
                  value={field.optionsCsv}
                  onChange={(e) => updateField(section.id, field.id, { optionsCsv: e.target.value })}
                />
              )}

              <div style={{ marginTop: 10, fontSize: 12 }}>
                {choiceFieldsBefore(section.id, field.id).length === 0 ? (
                  <span style={{ color: 'var(--ink-soft)' }}>Show only if… (add a choice question above this one, in the same category, to enable)</span>
                ) : (
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                    <span style={{ color: 'var(--ink-soft)' }}>Show only if</span>
                    <select
                      className="field-input"
                      style={{ width: 140, textAlign: 'left', fontSize: 12, padding: '5px 8px', maxWidth: 'none' }}
                      value={field.showOnlyIfFieldId}
                      onChange={(e) => updateField(section.id, field.id, { showOnlyIfFieldId: e.target.value, showOnlyIfValue: '' })}
                    >
                      <option value="">(no condition)</option>
                      {choiceFieldsBefore(section.id, field.id).map((f) => <option key={f.id} value={f.id}>{f.label || '(untitled)'}</option>)}
                    </select>
                    {field.showOnlyIfFieldId && (
                      <>
                        <span style={{ color: 'var(--ink-soft)' }}>
                          {section.fields.find((f) => f.id === field.showOnlyIfFieldId)?.type === 'checkboxgroup' ? 'includes' : 'equals'}
                        </span>
                        <input
                          className="field-input"
                          style={{ width: 120, textAlign: 'left', fontSize: 12, padding: '5px 8px', maxWidth: 'none' }}
                          placeholder="option value"
                          value={field.showOnlyIfValue}
                          onChange={(e) => updateField(section.id, field.id, { showOnlyIfValue: e.target.value })}
                        />
                      </>
                    )}
                  </div>
                )}
              </div>
            </div>
              );
            })
          );
        })()}

        <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
          <button className="btn" onClick={() => addField(sections[0].id)}>+ Add question</button>
          <button className="btn" onClick={() => setPickerOpenForSection(sections[0].id)}>📚 Choose from library</button>
        </div>
      </div>

      <div className="field-group" style={{ marginTop: 16 }}>
        <div className="field-label" style={{ marginBottom: 8 }}>
          Interpretation instructions
        </div>
        <textarea
          className="field-input"
          style={{ width: '100%', maxWidth: 'none', minHeight: 100, textAlign: 'left' }}
          placeholder="Describe how to interpret the answers, e.g. 'Flag as high risk if potassium is above 6 OR any two of the listed symptoms are present; otherwise routine monitoring.'"
          value={interpretationPrompt}
          onChange={(e) => setInterpretationPrompt(e.target.value)}
        />
        <p style={{ fontSize: 12, color: 'var(--ink-soft)', marginTop: 6 }}>
          This becomes the instruction Claude follows every time this assessment is
          calculated for a patient — be as specific as you would be briefing a colleague.
        </p>
      </div>

      <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
        <button className="btn" onClick={onBack}>
          Cancel
        </button>
        <button className="btn btn-primary" disabled={!canSave || saveMutation.isPending} onClick={handleSave}>
          {saveMutation.isPending ? 'Saving…' : isEditing ? 'Save new version' : 'Save assessment'}
        </button>
      </div>

      {saveMutation.isError && (
        <div className="result-card critical" style={{ marginTop: 16 }}>
          <div className="result-headline">Could not save: {(saveMutation.error as Error).message}</div>
        </div>
      )}
        </div>

        <div style={{ flex: 1, minWidth: 320 }}>
          <BuilderPreview title={title} blurb={blurb} sections={sections} />
        </div>
      </div>
    </div>
  );
}
