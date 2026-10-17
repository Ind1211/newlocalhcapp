import { useState } from 'react';
import { useQuestionLibrary, usePrograms, type QuestionLibraryItem } from '../hooks/useApi';

// Verified directly against the checkpoint's builderTypeToInternal() and
// draftFieldOptions() — yesno/radio collapse to pill (with synthesized Yes/No
// options, never stored in the source), dropdown becomes select, checkbox becomes
// checkboxgroup. Getting this wrong is exactly the bug class that regressed twice
// in the original build.
function translateType(fieldType: string): 'text' | 'textarea' | 'number' | 'pill' | 'checkboxgroup' | 'select' | 'scale' {
  if (fieldType === 'yesno' || fieldType === 'radio') return 'pill';
  if (fieldType === 'dropdown') return 'select';
  if (fieldType === 'checkbox') return 'checkboxgroup';
  if (fieldType === 'scale') return 'scale';
  if (fieldType === 'number') return 'number';
  if (fieldType === 'textarea') return 'textarea';
  return 'text';
}

function optionsToCsv(item: QuestionLibraryItem): string {
  if (item.field_type === 'yesno') return 'Yes, No';
  if (!item.options) return '';
  return item.options
    .map((o) => (typeof o === 'string' ? o : o.label))
    .filter(Boolean)
    .join(', ');
}

export interface PickedQuestion {
  label: string;
  type: 'text' | 'textarea' | 'number' | 'pill' | 'checkboxgroup' | 'select' | 'scale';
  optionsCsv: string;
}

export function LibraryPicker({
  programFilter,
  onAdd,
  onCancel,
}: {
  programFilter: string | null;
  onAdd: (questions: PickedQuestion[]) => void;
  onCancel: () => void;
}) {
  const [selectedProgram, setSelectedProgram] = useState<string | null>(programFilter);
  const library = useQuestionLibrary(selectedProgram);
  const programs = usePrograms();
  const [search, setSearch] = useState('');
  const [selectedItems, setSelectedItems] = useState<Record<string, QuestionLibraryItem>>({});

  const filtered = (library.data ?? []).filter(
    (item) => !search || item.label.toLowerCase().includes(search.toLowerCase()) || item.category.toLowerCase().includes(search.toLowerCase())
  );

  const grouped = new Map<string, QuestionLibraryItem[]>();
  for (const item of filtered) {
    if (!grouped.has(item.category)) grouped.set(item.category, []);
    grouped.get(item.category)!.push(item);
  }

  const selectedCount = Object.keys(selectedItems).length;

  const toggleItem = (item: QuestionLibraryItem) => {
    setSelectedItems((s) => {
      const next = { ...s };
      if (next[item.id]) delete next[item.id];
      else next[item.id] = item;
      return next;
    });
  };

  const handleAdd = () => {
    const chosen = Object.values(selectedItems).map((item) => ({
      label: item.label,
      type: translateType(item.field_type),
      optionsCsv: optionsToCsv(item),
    }));
    onAdd(chosen);
  };

  return (
    <div>
      <a className="back-link" onClick={onCancel}>
        ← Back to builder
      </a>
      <h2 style={{ margin: '16px 0 4px' }}>Choose from library</h2>
      <p style={{ color: 'var(--ink-soft)', fontSize: 13.5, marginTop: 0, marginBottom: 16 }}>
        Pick any questions to add — you can still edit their wording, type, or options
        afterward.
      </p>

      <input
        type="text"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search questions..."
        style={{
          maxWidth: 420,
          padding: '10px 14px',
          border: '1px solid var(--line)',
          borderRadius: 20,
          fontSize: 13.5,
          width: '100%',
          marginBottom: 14,
        }}
      />

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 20 }}>
        <button
          className={`tag ${selectedProgram === null ? 'tag-accent' : ''}`}
          style={{ cursor: 'pointer', fontFamily: 'var(--font-display)', border: selectedProgram === null ? 'none' : '1px solid var(--line)', background: selectedProgram === null ? undefined : 'var(--surface)' }}
          onClick={() => setSelectedProgram(null)}
        >
          All
        </button>
        {programs.data?.map((p) => (
          <button
            key={p.key}
            className={`tag ${selectedProgram === p.key ? 'tag-accent' : ''}`}
            style={{ cursor: 'pointer', fontFamily: 'var(--font-display)', border: selectedProgram === p.key ? 'none' : '1px solid var(--line)', background: selectedProgram === p.key ? undefined : 'var(--surface)' }}
            onClick={() => setSelectedProgram(p.key)}
          >
            {p.icon ? `${p.icon} ` : ''}{p.label}
          </button>
        ))}
      </div>

      {library.isLoading && <div className="empty-state">Loading question library…</div>}

      {[...grouped.entries()].map(([category, items]) => (
        <div key={category} style={{ marginBottom: 20 }}>
          <div
            style={{
              fontFamily: "'Inter', sans-serif",
              fontSize: 11.5,
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              color: 'var(--ink-soft)',
              marginBottom: 8,
            }}
          >
            {category}
          </div>
          {items.map((item) => (
            <label
              key={item.id}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 10,
                padding: '8px 0',
                borderTop: '1px solid var(--line-soft)',
                cursor: 'pointer',
              }}
            >
              <input
                type="checkbox"
                checked={!!selectedItems[item.id]}
                onChange={() => toggleItem(item)}
                style={{ marginTop: 3 }}
              />
              <div>
                <div style={{ fontSize: 13.5 }}>{item.label}</div>
                <div style={{ fontSize: 11, color: 'var(--ink-soft)', marginTop: 2 }}>{item.field_type}</div>
              </div>
            </label>
          ))}
        </div>
      ))}

      <div className="nav-row" style={{ position: 'sticky', bottom: 0, background: 'var(--canvas)', padding: '16px 0', display: 'flex', gap: 8 }}>
        <button className="btn" onClick={onCancel}>
          Cancel
        </button>
        <button className="btn btn-primary" disabled={selectedCount === 0} onClick={handleAdd}>
          Add {selectedCount} question{selectedCount === 1 ? '' : 's'} →
        </button>
      </div>
    </div>
  );
}
