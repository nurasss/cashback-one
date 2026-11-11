import type { InputHTMLAttributes, KeyboardEvent, WheelEvent } from 'react';

type NumericInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'inputMode'> & {
  allowNegative?: boolean;
  decimal?: boolean;
};

export function NumericInput({ allowNegative = false, decimal = false, onKeyDown, onWheel, ...props }: NumericInputProps) {
  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'e' || event.key === 'E' || event.key === '+' || (!allowNegative && event.key === '-')) {
      event.preventDefault();
    }
    onKeyDown?.(event);
  };

  const handleWheel = (event: WheelEvent<HTMLInputElement>) => {
    event.currentTarget.blur();
    onWheel?.(event);
  };

  return (
    <input
      {...props}
      type="number"
      inputMode={decimal ? 'decimal' : 'numeric'}
      onKeyDown={handleKeyDown}
      onWheel={handleWheel}
    />
  );
}
