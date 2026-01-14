import React from 'react';

// Hook to detect value changes and return flash class
function useDeltaFlash(value: number | string | undefined | null, epsilon = 1e-6) {
  const [flashClass, setFlashClass] = React.useState('');
  const prev = React.useRef<number | null>(null);

  React.useEffect(() => {
    if (value === undefined || value === null) return;
    const num = Number(value);
    if (Number.isNaN(num)) return;
    if (prev.current === null) {
      prev.current = num;
      return;
    }
    const delta = num - prev.current;
    prev.current = num;
    if (Math.abs(delta) <= epsilon) return;
    setFlashClass(delta > 0 ? 'flash-green' : 'flash-red');
    const t = setTimeout(() => setFlashClass(''), 950); // matches 0.85s animation with buffer
    return () => clearTimeout(t);
  }, [value, epsilon]);

  return flashClass;
}

export function DeltaFlash({
  value,
  className,
  children,
}: {
  value: number | string | undefined | null;
  className?: string;
  children: React.ReactNode;
}) {
  const flash = useDeltaFlash(value);
  const merged = [className, flash].filter(Boolean).join(' ');
  return <span className={merged}>{children}</span>;
}
