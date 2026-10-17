import { useEffect } from 'react';
import type { FieldDef, FieldOption } from '../types';
import { PillToggle } from './PillToggle';

type FieldValue = string | string[] | undefined;

// dropdown's options are plain strings; select/pill/checkboxgroup use {value,label}.
// This normalizes either shape to {value,label} so rendering code doesn't need to
// branch on it — the actual type distinction is handled once, here, not scattered.
function normalizeOptions(options: FieldOption[] | string[] | undefined): FieldOption[] {
  if (!options) return [];
  return options.map((opt) => (typeof opt === 'string' ? { value: opt, label: opt } : opt));
}

export function FieldRenderer({
  field,
  value,
  onChange,
}: {
  field: FieldDef;
  value: FieldValue;
  onChange: (v: FieldValue) => void;
}) {
  // A scale slider visually shows 5 as its default before it's touched, but the
  // underlying answer stays unset until onChange fires — meaning a required scale
  // field the person is genuinely happy leaving at 5 blocks Mark Complete forever,
  // with no visible reason why, since the slider already looks answered. Seeding
  // the real value to match what's already displayed fixes that without changing
  // what the slider shows.
  useEffect(() => {
    if (field.type === 'scale' && value === undefined) {
      onChange('5');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [field.name]);

  switch (field.type) {
    case 'pill':
      return (
        <PillToggle
          options={normalizeOptions(field.options)}
          value={typeof value === 'string' ? value : undefined}
          onChange={(v) => onChange(v)}
        />
      );

    case 'select':
    case 'dropdown':
      return (
        <select
          className="field-input"
          style={{ width: '320px', textAlign: 'left' }}
          value={typeof value === 'string' ? value : ''}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="" disabled>
            Select…
          </option>
          {normalizeOptions(field.options).map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      );

    case 'checkboxgroup': {
      const selected = Array.isArray(value) ? value : [];
      const opts = normalizeOptions(field.options);
      const toggle = (optValue: string) => {
        if (optValue === 'none') {
          onChange(['none']);
          return;
        }
        const withoutNone = selected.filter((v) => v !== 'none');
        onChange(
          withoutNone.includes(optValue)
            ? withoutNone.filter((v) => v !== optValue)
            : [...withoutNone, optValue]
        );
      };
      return (
        <div className="pill-toggle" style={{ flexWrap: 'wrap', justifyContent: 'flex-start' }}>
          {opts.map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={selected.includes(opt.value) ? 'selected' : ''}
              onClick={() => toggle(opt.value)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      );
    }

    case 'date':
      return (
        <input
          className="field-input"
          type="date"
          style={{ width: '320px' }}
          value={typeof value === 'string' ? value : ''}
          onChange={(e) => onChange(e.target.value)}
        />
      );

    case 'number':
      return (
        <input
          className="field-input"
          type="number"
          style={{ width: '320px' }}
          value={typeof value === 'string' ? value : ''}
          placeholder={field.placeholder}
          onChange={(e) => onChange(e.target.value)}
        />
      );

    case 'scale': {
      const current = typeof value === 'string' && value !== '' ? Number(value) : 5;
      return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, width: 220 }}>
          <input
            type="range"
            min={0}
            max={10}
            step={1}
            value={current}
            onChange={(e) => onChange(e.target.value)}
            style={{ flex: 1 }}
          />
          <span style={{ fontFamily: "'Inter', sans-serif", fontSize: 13, minWidth: 18, textAlign: 'right' }}>
            {current}
          </span>
        </div>
      );
    }

    case 'textarea':
      return (
        <textarea
          className="field-input"
          style={{ width: '320px', textAlign: 'left', minHeight: 60 }}
          value={typeof value === 'string' ? value : ''}
          placeholder={field.placeholder}
          onChange={(e) => onChange(e.target.value)}
        />
      );

    case 'text':
    default:
      return (
        <input
          className="field-input"
          type="text"
          style={{ width: '320px', textAlign: 'left' }}
          value={typeof value === 'string' ? value : ''}
          placeholder={field.placeholder}
          onChange={(e) => onChange(e.target.value)}
        />
      );
  }
}
