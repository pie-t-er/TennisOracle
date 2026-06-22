"use client";

import { useEffect, useRef, useState } from "react";
import { getPlayers, Player } from "@/lib/api";

interface Props {
  label: string;
  value: string;
  onChange: (name: string) => void;
  exclude?: string; // hide this player from results
}

export default function PlayerSearch({ label, value, onChange, exclude }: Props) {
  const [query, setQuery] = useState(value);
  const [options, setOptions] = useState<Player[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const containerRef = useRef<HTMLDivElement>(null);

  // Sync display when value changes externally
  useEffect(() => {
    setQuery(value);
  }, [value]);

  // Debounced search
  useEffect(() => {
    clearTimeout(debounceRef.current);
    if (query.length < 2) {
      setOptions([]);
      setOpen(false);
      return;
    }
    setLoading(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const results = await getPlayers(query, 10);
        setOptions(results.filter((p) => p.name !== exclude));
        setOpen(true);
      } catch {
        setOptions([]);
      } finally {
        setLoading(false);
      }
    }, 220);
  }, [query, exclude]);

  // Close on outside click
  useEffect(() => {
    function handle(e: MouseEvent) {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, []);

  function select(player: Player) {
    setQuery(player.name);
    onChange(player.name);
    setOpen(false);
  }

  function clear() {
    setQuery("");
    onChange("");
    setOptions([]);
    setOpen(false);
  }

  return (
    <div ref={containerRef} className="relative w-full">
      <label className="block text-xs font-medium text-gray-500 mb-1.5 uppercase tracking-wide">
        {label}
      </label>
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            if (!e.target.value) onChange("");
          }}
          onFocus={() => options.length > 0 && setOpen(true)}
          placeholder="Search player name…"
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-sm
                     placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors pr-8"
        />
        {query && (
          <button
            onClick={clear}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
            aria-label="Clear"
          >
            ✕
          </button>
        )}
        {loading && (
          <span className="absolute right-8 top-1/2 -translate-y-1/2 text-xs text-gray-500">
            …
          </span>
        )}
      </div>

      {open && options.length > 0 && (
        <ul className="absolute z-50 mt-1 w-full bg-gray-800 border border-gray-700 rounded-lg
                       shadow-xl overflow-hidden max-h-64 overflow-y-auto">
          {options.map((p) => (
            <li key={p.name}>
              <button
                onMouseDown={() => select(p)}
                className="w-full text-left px-4 py-2.5 hover:bg-gray-700 flex items-center justify-between
                           text-sm transition-colors"
              >
                <span className="font-medium">{p.name}</span>
                <span className="text-gray-500 text-xs">
                  {p.rank ? `#${p.rank}` : "—"} · {p.country}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
