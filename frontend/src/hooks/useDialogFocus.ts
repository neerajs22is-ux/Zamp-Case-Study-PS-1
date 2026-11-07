import { useEffect, useRef } from "react";

// Only the most recently opened overlay handles Escape and traps focus.
const overlays: symbol[] = [];
let bodyLocks = 0;
let previousOverflow = "";
const focusable =
  'a[href],button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex]:not([tabindex="-1"])';
export function useDialogFocus(open: boolean, onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  const close = useRef(onClose);
  useEffect(() => {
    close.current = onClose;
  }, [onClose]);
  useEffect(() => {
    if (!open) return;
    const panel = ref.current;
    if (!panel) return;
    const token = Symbol("overlay");
    const returnTo = document.activeElement as HTMLElement | null;
    overlays.push(token);
    if (bodyLocks++ === 0) {
      previousOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
    }
    const controls = () =>
      Array.from(panel.querySelectorAll<HTMLElement>(focusable)).filter(
        (el) =>
          el.getClientRects().length > 0 && !el.closest("[hidden],[inert]"),
      );
    (controls()[0] || panel).focus();
    const handle = (event: KeyboardEvent) => {
      if (overlays[overlays.length - 1] !== token) return;
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopImmediatePropagation();
        close.current();
        return;
      }
      if (event.key !== "Tab") return;
      const items = controls();
      const index = items.indexOf(document.activeElement as HTMLElement);
      if (!items.length) {
        event.preventDefault();
        panel.focus();
      } else if (event.shiftKey && index <= 0) {
        event.preventDefault();
        items[items.length - 1].focus();
      } else if (!event.shiftKey && (index === items.length - 1 || index < 0)) {
        event.preventDefault();
        items[0].focus();
      }
    };
    document.addEventListener("keydown", handle, true);
    return () => {
      document.removeEventListener("keydown", handle, true);
      const index = overlays.indexOf(token);
      if (index !== -1) overlays.splice(index, 1);
      if (--bodyLocks === 0) document.body.style.overflow = previousOverflow;
      if (returnTo?.isConnected) returnTo.focus();
    };
  }, [open]);
  return ref;
}
