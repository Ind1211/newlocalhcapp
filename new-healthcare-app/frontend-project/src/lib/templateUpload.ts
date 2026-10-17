// Ported directly from the checkpoint's validateUploadTemplate() / normalizeUploadTemplate() —
// these are what let someone drop in a JSON template from another system rather
// than build one field-by-field.

export const UPLOAD_ALLOWED_TYPES = ['text', 'textarea', 'radio', 'dropdown', 'checkbox', 'number', 'scale', 'date'];
export const UPLOAD_OPTION_TYPES = ['radio', 'dropdown', 'checkbox'];

interface RawQuestion {
  id?: string;
  label?: string;
  type?: string;
  required?: boolean;
  section?: string;
  category?: string;
  options?: (string | { label: string; value?: string })[];
  showIf?: { id?: string; equals?: string; includes?: string };
}

interface RawSection {
  key?: string;
  title?: string;
  desc?: string;
}

interface RawTemplate {
  name?: string;
  title?: string;
  description?: string;
  blurb?: string;
  interpretationPrompt?: string;
  questions?: RawQuestion[];
  fields?: RawQuestion[];
  sections?: RawSection[];
  categories?: RawSection[];
}

export interface NormalizedField {
  name: string;
  label: string;
  type: 'text' | 'textarea' | 'pill' | 'select' | 'checkboxgroup' | 'number' | 'scale' | 'date';
  section: string;
  required: boolean;
  options?: { value: string; label: string }[];
  show_only_if?: { field: string; equals?: string; includes?: string } | null;
}

export interface NormalizedTemplate {
  title: string;
  blurb: string;
  sections: { key: string; title: string; desc: string }[];
  fields: NormalizedField[];
  interpretationPrompt: string;
}

// Mirrors builderTypeToInternal() exactly — same mapping, same fallthrough.
function builderTypeToInternal(t: string): NormalizedField['type'] {
  if (t === 'yesno' || t === 'radio') return 'pill';
  if (t === 'dropdown') return 'select';
  if (t === 'checkbox') return 'checkboxgroup';
  return t as NormalizedField['type'];
}

export function validateUploadTemplate(obj: unknown): string[] {
  const errors: string[] = [];
  if (typeof obj !== 'object' || obj === null || Array.isArray(obj)) {
    errors.push('The template root must be a JSON object.');
    return errors;
  }
  const template = obj as RawTemplate;
  const questions = template.questions ?? template.fields;
  if (!Array.isArray(questions) || questions.length === 0) {
    errors.push('Template must include a non-empty "questions" array.');
    return errors;
  }
  const sectionsRaw = template.sections ?? template.categories;
  let sectionKeys: (string | undefined)[] | null = null;
  if (sectionsRaw !== undefined) {
    if (!Array.isArray(sectionsRaw) || sectionsRaw.length === 0) {
      errors.push('"sections", if present, must be a non-empty array of {key, title}.');
    } else {
      sectionKeys = sectionsRaw.map((s) => s?.key);
      sectionsRaw.forEach((s, i) => {
        if (!s || typeof s.key !== 'string' || !s.key.trim()) errors.push(`Section ${i + 1}: missing a "key".`);
        if (!s || typeof s.title !== 'string' || !s.title.trim()) errors.push(`Section ${i + 1}: missing a "title".`);
      });
    }
  }
  const questionIds = questions.map((q, i) => q?.id ?? `q${i}`);
  questions.forEach((q, i) => {
    const label = q?.label ?? `Question ${i + 1}`;
    if (!q || typeof q.label !== 'string' || !q.label.trim()) errors.push(`Question ${i + 1}: missing a "label".`);
    if (!q || !q.type || !UPLOAD_ALLOWED_TYPES.includes(q.type)) {
      errors.push(`"${label}": type "${q?.type ?? 'undefined'}" is not supported. Use one of: ${UPLOAD_ALLOWED_TYPES.join(', ')}.`);
    } else if (UPLOAD_OPTION_TYPES.includes(q.type)) {
      if (!Array.isArray(q.options) || q.options.length === 0) errors.push(`"${label}": type "${q.type}" requires a non-empty "options" array.`);
    }
    const qSection = q?.section ?? q?.category;
    if (qSection && sectionKeys && !sectionKeys.includes(qSection)) errors.push(`"${label}": section "${qSection}" is not one of the declared sections.`);
    if (q?.showIf) {
      if (!q.showIf.id || !questionIds.slice(0, i).includes(q.showIf.id)) errors.push(`"${label}": showIf.id must reference an earlier question's id.`);
      if (q.showIf.equals === undefined && q.showIf.includes === undefined) errors.push(`"${label}": showIf needs an "equals" or "includes" value.`);
    }
  });
  return errors;
}

export function normalizeUploadTemplate(obj: RawTemplate): NormalizedTemplate {
  const sectionsRaw = obj.sections ?? obj.categories;
  const sections =
    Array.isArray(sectionsRaw) && sectionsRaw.length
      ? sectionsRaw.map((s) => ({ key: s.key!, title: s.title!, desc: s.desc ?? '' }))
      : [{ key: 'main', title: obj.name ?? 'Untitled assessment', desc: '' }];
  const defaultKey = sections[0].key;
  const questionsRaw = obj.questions ?? obj.fields ?? [];

  const idToName: Record<string, string> = {};
  questionsRaw.forEach((q, i) => {
    idToName[q.id ?? `q${i}`] = `f${i}`;
  });

  const fields: NormalizedField[] = questionsRaw.map((q, i) => {
    const out: NormalizedField = {
      name: `f${i}`,
      label: q.label!,
      type: builderTypeToInternal(q.type!),
      section: q.section ?? q.category ?? defaultKey,
      required: !!q.required,
      options: q.type && UPLOAD_OPTION_TYPES.includes(q.type)
        ? (q.options ?? []).map((o) => (typeof o === 'string' ? { value: o, label: o } : { value: o.label, label: o.label }))
        : undefined,
    };
    if (q.showIf?.id) {
      out.show_only_if = { field: idToName[q.showIf.id] ?? q.showIf.id, equals: q.showIf.equals, includes: q.showIf.includes };
    }
    return out;
  });

  return {
    title: obj.name ?? obj.title ?? 'Untitled assessment',
    blurb: obj.description ?? obj.blurb ?? '',
    sections,
    fields,
    interpretationPrompt: obj.interpretationPrompt ?? '',
  };
}
