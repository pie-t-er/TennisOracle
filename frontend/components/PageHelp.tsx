"use client";

import { useState, useEffect, useCallback } from "react";
import { Joyride, Step, STATUS, EventData } from "react-joyride";
import FeedbackModal from "./FeedbackModal";

const JOYRIDE_OPTIONS = {
  backgroundColor:    "#111827",
  arrowColor:         "#111827",
  textColor:          "#e5e7eb",
  primaryColor:       "#10b981",
  overlayColor:       "rgba(0,0,0,0.6)",
  buttons:            ["back", "primary", "skip"] as ("back" | "primary" | "skip")[],
  showProgress:       true,
  overlayClickAction: false as const,
  skipBeacon:         true,
  scrollOffset:       80,
};

const JOYRIDE_STYLES = {
  tooltip: {
    borderRadius: 10,
    border: "1px solid #374151",
  },
  buttonBack:    { color: "#9ca3af" },
  buttonSkip:    { color: "#6b7280", fontSize: "0.8rem" },
  buttonPrimary: { borderRadius: 6 },
};

const BTN =
  "w-10 h-10 rounded-full border border-gray-700 bg-gray-900/90 backdrop-blur-sm shadow-lg " +
  "flex items-center justify-center transition-colors";

export default function PageHelp({ steps }: { steps: Step[] }) {
  const [run,          setRun]          = useState(false);
  const [mounted,      setMounted]      = useState(false);
  const [feedbackOpen, setFeedbackOpen] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  const handleEvent = useCallback((data: EventData) => {
    if (data.status === STATUS.FINISHED || data.status === STATUS.SKIPPED) {
      setRun(false);
    }
  }, []);

  return (
    <>
      {mounted && (
        <Joyride
          steps={steps}
          run={run}
          continuous
          onEvent={handleEvent}
          options={JOYRIDE_OPTIONS}
          styles={JOYRIDE_STYLES}
        />
      )}

      {feedbackOpen && (
        <FeedbackModal onClose={() => setFeedbackOpen(false)} />
      )}

      <div
        id="page-help"
        className="fixed bottom-5 right-5 z-40 flex flex-col gap-2"
      >
        {/* Walkthrough */}
        <button
          onClick={() => setRun(true)}
          title="Page walkthrough"
          className={`${BTN} text-gray-500 hover:text-yellow-400 hover:border-yellow-600/60 text-sm font-bold select-none`}
        >
          ?
        </button>

        {/* Feedback / bug report */}
        <button
          onClick={() => setFeedbackOpen(true)}
          title="Send feedback or report a bug"
          className={`${BTN} text-gray-500 hover:text-red-400 hover:border-red-700/60`}
        >
          <svg viewBox="0 0 16 16" fill="currentColor" className="w-4 h-4">
            {/* pole */}
            <path d="M2.5 1.25h1v13.5h-1z"/>
            {/* flag body with triangle notch */}
            <path d="M3.5 2.5h8.5l-2 3 2 3H3.5V2.5z"/>
          </svg>
        </button>
      </div>
    </>
  );
}
