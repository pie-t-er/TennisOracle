"use client";

import { useState, useEffect, useCallback } from "react";
import { submitFeedback, FeedbackRequest } from "@/lib/api";

type FeedbackType = FeedbackRequest["type"];

const TYPES: { value: FeedbackType; label: string; hint: string }[] = [
  { value: "bug",     label: "Bug",            hint: "Something isn't working as expected" },
  { value: "feature", label: "Feature request", hint: "An idea for something new or improved"  },
  { value: "insight", label: "User insight",    hint: "General feedback or observation"         },
];

interface Props {
  onClose: () => void;
}

export default function FeedbackModal({ onClose }: Props) {
  const [type,        setType]        = useState<FeedbackType>("bug");
  const [description, setDescription] = useState("");
  const [loading,     setLoading]     = useState(false);
  const [error,       setError]       = useState<string | null>(null);
  const [result,      setResult]      = useState<{ url: string; number: number } | null>(null);

  const handleClose = useCallback(() => onClose(), [onClose]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") handleClose(); };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [handleClose]);

  async function handleSubmit() {
    const trimmed = description.trim();
    if (!trimmed) { setError("Please add a description."); return; }
    setLoading(true);
    setError(null);
    try {
      const res = await submitFeedback({ type, description: trimmed });
      setResult({ url: res.issue_url, number: res.issue_number });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Submission failed — try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
      onClick={handleClose}
    >
      <div
        className="w-full max-w-md bg-gray-900 border border-gray-800 rounded-2xl shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-6 pb-4 border-b border-gray-800">
          <h2 className="text-base font-semibold text-gray-100">
            {result ? "Feedback submitted" : "Send feedback"}
          </h2>
          <button
            onClick={handleClose}
            aria-label="Close"
            className="w-7 h-7 rounded-full text-gray-500 hover:text-gray-200 hover:bg-gray-800 flex items-center justify-center text-lg leading-none transition-colors"
          >
            ✕
          </button>
        </div>

        {result ? (
          /* ── Success view ── */
          <div className="px-6 py-8 space-y-5 text-center">
            <div className="text-4xl">✓</div>
            <div className="space-y-1">
              <p className="text-gray-200 font-medium">Issue #{result.number} created</p>
              <p className="text-gray-500 text-sm">
                Thanks — it's been logged to the project backlog.
              </p>
            </div>
            <a
              href={result.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-emerald-400 hover:text-emerald-300 text-sm font-medium transition-colors"
            >
              View on GitHub
              <svg viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
                <path d="M3.75 2h8.5c.966 0 1.75.784 1.75 1.75v8.5A1.75 1.75 0 0 1 12.25 14h-8.5A1.75 1.75 0 0 1 2 12.25v-8.5C2 2.784 2.784 2 3.75 2zm0 1.5a.25.25 0 0 0-.25.25v8.5c0 .138.112.25.25.25h8.5a.25.25 0 0 0 .25-.25v-8.5a.25.25 0 0 0-.25-.25h-8.5zM6.25 7.5a.75.75 0 0 1 .75-.75H10a.75.75 0 0 1 0 1.5H7.56l2.97 2.97a.749.749 0 1 1-1.06 1.06L6.5 9.31v2.44a.75.75 0 0 1-1.5 0V8a.75.75 0 0 1 .75-.75H6z"/>
              </svg>
            </a>
            <button
              onClick={handleClose}
              className="block w-full mt-2 py-2 text-sm text-gray-500 hover:text-gray-300 transition-colors"
            >
              Close
            </button>
          </div>
        ) : (
          /* ── Form view ── */
          <div className="px-6 py-5 space-y-5">

            {/* Type selector */}
            <div className="space-y-2">
              <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Type</p>
              <div className="grid grid-cols-3 gap-2">
                {TYPES.map(({ value, label }) => (
                  <button
                    key={value}
                    onClick={() => setType(value)}
                    className={`py-2 px-3 rounded-lg text-xs font-medium border transition-colors text-center ${
                      type === value
                        ? "bg-emerald-900/50 border-emerald-700/70 text-emerald-300"
                        : "bg-gray-800/60 border-gray-700/50 text-gray-400 hover:text-gray-200"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <p className="text-[11px] text-gray-600">
                {TYPES.find((t) => t.value === type)?.hint}
              </p>
            </div>

            {/* Description */}
            <div className="space-y-2">
              <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Description</p>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={
                  type === "bug"
                    ? "What happened? What did you expect instead?"
                    : type === "feature"
                    ? "Describe the feature or improvement…"
                    : "Share your observation or feedback…"
                }
                rows={5}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-emerald-600 resize-none"
              />
            </div>

            {error && (
              <p className="text-red-400 text-xs">{error}</p>
            )}

            {/* Submit */}
            <button
              onClick={handleSubmit}
              disabled={loading || !description.trim()}
              className="w-full py-2.5 rounded-lg bg-emerald-700 hover:bg-emerald-600 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
            >
              {loading ? "Submitting…" : "Submit"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
