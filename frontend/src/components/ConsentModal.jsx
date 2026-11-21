import { useState } from "react";

export default function ConsentModal({ open, onAccept, onCancel }) {
  const [checked, setChecked] = useState(false);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm" role="dialog" aria-modal="true">
      <div className="fade-in max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-slate-700 bg-ink-900 p-6 shadow-glow">
        <h2 className="text-lg font-semibold text-slate-50">Before we start: your consent</h2>
        <p className="mt-2 text-sm text-slate-300">
          BehaviorSense measures <em>how</em> you use this page, never <em>what</em> you type.
        </p>
        <div className="mt-4 grid gap-4 text-sm sm:grid-cols-2">
          <div>
            <h3 className="font-medium text-emerald-300">What is collected (per minute)</h3>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-slate-300">
              <li>Counts of keystrokes, corrections, spaces, arrow/shortcut keys</li>
              <li>Mouse movement distance, clicks, drags, scroll bursts</li>
              <li>Typing-interval statistics and idle seconds</li>
              <li>How often this page lost focus or was hidden</li>
            </ul>
          </div>
          <div>
            <h3 className="font-medium text-rose-300">What is never collected</h3>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-slate-300">
              <li>Typed text or which keys you pressed</li>
              <li>Passwords (password fields are ignored)</li>
              <li>Messages, page content, URLs, window titles</li>
              <li>Anything outside this browser tab</li>
            </ul>
          </div>
        </div>
        <ul className="mt-4 space-y-1 text-xs text-slate-400">
          <li>- You can stop at any time; a partial minute is discarded.</li>
          <li>- You can delete any session, or all your data, from the History page.</li>
          <li>- Estimates are an experimental research output, <strong>not a medical or psychological diagnosis</strong>.</li>
          <li>- Only use this on your own device or where you are authorised to do so.</li>
        </ul>
        <label className="mt-5 flex cursor-pointer items-start gap-3 text-sm text-slate-200">
          <input type="checkbox" className="mt-1 h-4 w-4 accent-indigo-400" checked={checked} onChange={(e) => setChecked(e.target.checked)} />
          I understand and agree to monitoring of my interaction patterns on this page.
        </label>
        <div className="mt-6 flex justify-end gap-3">
          <button className="rounded-xl px-4 py-2 text-sm text-slate-300 transition hover:bg-slate-800" onClick={() => { setChecked(false); onCancel(); }}>
            Cancel
          </button>
          <button
            disabled={!checked}
            className="rounded-xl bg-indigo-500 px-4 py-2 text-sm font-medium text-white transition enabled:hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-40"
            onClick={() => { setChecked(false); onAccept(); }}
          >
            Agree and start
          </button>
        </div>
      </div>
    </div>
  );
}
