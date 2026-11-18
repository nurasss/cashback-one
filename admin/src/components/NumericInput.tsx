import type { ClipboardEvent, InputHTMLAttributes, KeyboardEvent, WheelEvent } from 'react';

type NumericInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'inputMode'> & {
  allowNegative?: boolean;
  decimal?: boolean;
};

const TRIM_SPACES_RE = /^[\s\u00A0\u202F]+|[\s\u00A0\u202F]+$/g;
const VALID_GROUPED_INT_RE = /^\d{1,3}(?:([ \u00A0\u202F])\d{3})(?:\1\d{3})*$/;

export function normalizeNumericPaste(raw: string, decimal: boolean, allowNegative: boolean): string | null {
  const trimmed = raw.replace(TRIM_SPACES_RE, '');
  if (!trimmed) return null;

  let body = trimmed;
  let negative = false;
  if (body.startsWith('-') || body.startsWith('\u2212')) {
    if (!allowNegative) return null;
    negative = true;
    body = body.slice(1);
    if (!body) return null;
  }

  // Only ASCII digits, decimal separators ('.' or ','), and grouping spaces are permitted.
  // Exponents (e/E), extra signs (+/-), currency symbols, letters, etc. must be rejected, not stripped.
  if (/[^0-9., \u00A0\u202F]/.test(body)) {
    return null;
  }

  const sepMatches = body.match(/[.,]/g);
  const sepCount = sepMatches ? sepMatches.length : 0;

  if (!decimal) {
    if (sepCount > 0) return null;
    let digits: string;
    if (/^\d+$/.test(body)) {
      digits = body;
    } else if (VALID_GROUPED_INT_RE.test(body)) {
      digits = body.replace(/[ \u00A0\u202F]/g, '');
    } else {
      return null;
    }
    const isZero = /^0+$/.test(digits);
    return negative && !isZero ? `-${digits}` : digits;
  }

  if (sepCount > 1) return null;

  let intRaw = body;
  let fracRaw: string | null = null;
  if (sepCount === 1) {
    const sepIndex = body.search(/[.,]/);
    intRaw = body.slice(0, sepIndex);
    fracRaw = body.slice(sepIndex + 1);
    if (!intRaw || !fracRaw || !/^\d+$/.test(fracRaw)) {
      return null;
    }
  }

  let intDigits: string;
  if (/^\d+$/.test(intRaw)) {
    intDigits = intRaw;
  } else if (VALID_GROUPED_INT_RE.test(intRaw)) {
    intDigits = intRaw.replace(/[ \u00A0\u202F]/g, '');
  } else {
    return null;
  }

  const normalized = fracRaw !== null ? `${intDigits}.${fracRaw}` : intDigits;
  if (!negative) return normalized;
  const isZero = /^0+$/.test(intDigits) && (fracRaw === null || /^0+$/.test(fracRaw));
  return isZero ? normalized : `-${normalized}`;
}

function setInputValue(input: HTMLInputElement, value: string): void {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
  if (setter) {
    try {
      setter.call(input, value);
      return;
    } catch {
      // Fall through to direct property assignment
    }
  }
  try {
    input.value = value;
  } catch {
    // Ignore if assignment throws
  }
}

export function NumericInput({
  allowNegative = false,
  decimal = false,
  onKeyDown,
  onWheel,
  onPaste,
  step,
  ...props
}: NumericInputProps) {
  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (
      event.key === 'e' ||
      event.key === 'E' ||
      event.key === '+' ||
      (!allowNegative && (event.key === '-' || event.key === '\u2212'))
    ) {
      event.preventDefault();
    }
    onKeyDown?.(event);
  };

  const handleWheel = (event: WheelEvent<HTMLInputElement>) => {
    event.currentTarget.blur();
    onWheel?.(event);
  };

  const handlePaste = (event: ClipboardEvent<HTMLInputElement>) => {
    onPaste?.(event);
    if (event.defaultPrevented) return;
    const raw = event.clipboardData?.getData('text') ?? '';
    if (!raw) return;

    const normalized = normalizeNumericPaste(raw, decimal, allowNegative);
    if (normalized === null) {
      event.preventDefault();
      return;
    }

    const input = event.currentTarget;
    const prevValue = input.value;

    let selStart: number | null = null;
    let selEnd: number | null = null;
    try {
      if (typeof input.selectionStart === 'number' && typeof input.selectionEnd === 'number') {
        selStart = input.selectionStart;
        selEnd = input.selectionEnd;
      }
    } catch {
      // HTMLInputElement[type="number"] throws/returns null for selectionStart/End
    }

    if (selStart !== null && selEnd !== null) {
      const candidate = prevValue.slice(0, selStart) + normalized + prevValue.slice(selEnd);
      if (normalizeNumericPaste(candidate, decimal, allowNegative) === null) {
        event.preventDefault();
        return;
      }
      if (normalized === raw) {
        return;
      }
      event.preventDefault();
      setInputValue(input, candidate);
      input.dispatchEvent(new Event('input', { bubbles: true }));
      const nextCaret = selStart + normalized.length;
      try {
        input.setSelectionRange(nextCaret, nextCaret);
      } catch {
        // Ignore if input type rejects setSelectionRange
      }
      return;
    }

    const rawSelText = typeof window !== 'undefined' ? (window.getSelection?.()?.toString() ?? '') : '';
    const selText = rawSelText && prevValue.includes(rawSelText) ? rawSelText : '';

    // Prevent gluing two individually valid decimal numbers into a double-decimal number (e.g. 2.5 + 1.5 -> 2.515 in Chrome)
    if (decimal && normalized.includes('.') && prevValue.includes('.') && !selText.includes('.')) {
      event.preventDefault();
      return;
    }

    // Prevent gluing a negative sign into an existing negative number unless the existing minus is selected/replaced
    if (normalized.startsWith('-') && prevValue.startsWith('-') && !selText.startsWith('-')) {
      event.preventDefault();
      return;
    }

    const needsNegativeGuard =
      allowNegative &&
      prevValue !== '' &&
      selText !== prevValue &&
      (normalized.startsWith('-') || prevValue.startsWith('-'));

    // Unformatted valid paste with no combination risk: let native browser paste handle caret/selection cleanly
    if (normalized === raw && !needsNegativeGuard) {
      return;
    }

    event.preventDefault();

    if (prevValue === '') {
      setInputValue(input, normalized);
      input.dispatchEvent(new Event('input', { bubbles: true }));
      return;
    }

    if (typeof document !== 'undefined' && typeof document.execCommand === 'function') {
      let suppressed = true;
      let shouldDispatchInput = false;
      const blockDuringProbe = (e: Event) => {
        if (suppressed) {
          e.stopImmediatePropagation?.();
        }
      };
      const hasListeners =
        typeof input.addEventListener === 'function' && typeof input.removeEventListener === 'function';
      if (hasListeners) {
        input.addEventListener('input', blockDuringProbe, true);
      }
      let inserted = false;
      try {
        inserted = Boolean(document.execCommand('insertText', false, normalized));
        if (inserted) {
          const afterValue = input.value;
          const bad = Boolean(input.validity?.badInput);
          const invalidCombined =
            bad || (afterValue !== '' && normalizeNumericPaste(afterValue, decimal, allowNegative) === null);
          if (invalidCombined) {
            let restored = false;
            if (afterValue !== prevValue || bad) {
              const undone = Boolean(document.execCommand('undo'));
              const postUndoValue = input.value;
              const postUndoBad = Boolean(input.validity?.badInput);
              if (undone && postUndoValue === prevValue && !postUndoBad) {
                restored = true;
              }
            } else {
              restored = true;
            }

            if (!restored) {
              setInputValue(input, prevValue);
            }
          } else if (afterValue !== prevValue) {
            shouldDispatchInput = true;
          }
        }
      } catch {
        inserted = false;
      } finally {
        suppressed = false;
        if (hasListeners) {
          input.removeEventListener('input', blockDuringProbe, true);
        }
      }

      if (inserted) {
        if (shouldDispatchInput) {
          input.dispatchEvent(new Event('input', { bubbles: true }));
        }
        return;
      }

      if (input.value !== prevValue) {
        setInputValue(input, prevValue);
      }
      return;
    }

    // Positional paste is technically unavailable in this environment (selectionStart/End is null
    // and document.execCommand is absent/unsupported). Safely preserve the original value without
    // blindly replacing the entire field or desynchronizing controlled state / submitted payloads.
    if (input.value !== prevValue) {
      setInputValue(input, prevValue);
    }
  };

  return (
    <input
      {...props}
      type="number"
      step={decimal ? (step ?? 'any') : step}
      inputMode={decimal ? 'decimal' : 'numeric'}
      onKeyDown={handleKeyDown}
      onWheel={handleWheel}
      onPaste={handlePaste}
    />
  );
}
