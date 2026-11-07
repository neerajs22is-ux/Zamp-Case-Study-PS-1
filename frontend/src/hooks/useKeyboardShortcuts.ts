import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";

interface KeyboardShortcutOptions {
  onToggleShortcutsHelp?: () => void;
  onEscape?: () => void;
  enabled?: boolean;
}

export function useKeyboardShortcuts({
  onToggleShortcutsHelp,
  onEscape,
  enabled = true,
}: KeyboardShortcutOptions = {}) {
  const navigate = useNavigate();
  const lastKeyRef = useRef<{ key: string; time: number } | null>(null);

  useEffect(() => {
    if (!enabled) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // 1. Guard: Ignore shortcuts when the user is typing in form inputs
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable)
      ) {
        // Allow Esc even inside inputs to blur or close
        if (e.key === "Escape" && onEscape) {
          target.blur();
          onEscape();
        }
        return;
      }

      // Ignore modifier combinations (Ctrl, Alt, Meta) for single-key shortcuts
      if (e.ctrlKey || e.altKey || e.metaKey) {
        return;
      }

      const now = Date.now();
      const lastKey = lastKeyRef.current;

      // 2. Escape: Close active overlays / drawers
      if (e.key === "Escape") {
        if (onEscape) {
          onEscape();
        }
        lastKeyRef.current = null;
        return;
      }

      if (document.querySelector('[role="dialog"][aria-modal="true"]')) return;

      // 3. '?' (Shift + /): Toggle Keyboard Shortcuts Help
      if (e.key === "?" || (e.shiftKey && e.key === "/")) {
        e.preventDefault();
        if (onToggleShortcutsHelp) {
          onToggleShortcutsHelp();
        }
        lastKeyRef.current = null;
        return;
      }

      // 4. '/': Focus primary search or filter input on page
      if (e.key === "/") {
        e.preventDefault();
        const searchInput = document.querySelector<HTMLInputElement>(
          'input[placeholder*="Search" i], input[placeholder*="Filter" i]',
        );
        if (searchInput) {
          searchInput.focus();
          searchInput.select();
        }
        lastKeyRef.current = null;
        return;
      }

      // 5. 'g' then <key> Navigation Sequences (1000ms window)
      if (lastKey && lastKey.key === "g" && now - lastKey.time < 1200) {
        lastKeyRef.current = null;
        switch (e.key.toLowerCase()) {
          case "t":
            e.preventDefault();
            navigate("/today");
            return;
          case "i":
            e.preventDefault();
            navigate("/invoices");
            return;
          case "a":
            e.preventDefault();
            navigate("/approvals");
            return;
          case "u":
            e.preventDefault();
            navigate("/audit");
            return;
          case "s":
            e.preventDefault();
            navigate("/setup");
            return;
          case "c":
            e.preventDefault();
            navigate("/settings/connections");
            return;
          case "r":
            e.preventDefault();
            navigate("/settings/reference-data");
            return;
          case "m":
            e.preventDefault();
            navigate("/settings/team");
            return;
          default:
            break;
        }
      }

      // Record 'g' keypress for sequence
      if (e.key.toLowerCase() === "g") {
        lastKeyRef.current = { key: "g", time: now };
        return;
      }

      // Clear recorded key if any other key is pressed
      lastKeyRef.current = null;
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [navigate, onToggleShortcutsHelp, onEscape, enabled]);
}
