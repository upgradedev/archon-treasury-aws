import { RefObject, useEffect } from 'react';

export function useOutsideClick<T extends HTMLElement>(
  ref: RefObject<T>,
  onOutsideClick: () => void,
): void {
  useEffect(() => {
    const handlePointerDown = (event: MouseEvent | TouchEvent) => {
      const el = ref.current;
      if (!el || el.contains(event.target as Node)) {
        return;
      }
      onOutsideClick();
    };
    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('touchstart', handlePointerDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('touchstart', handlePointerDown);
    };
  }, [ref, onOutsideClick]);
}
