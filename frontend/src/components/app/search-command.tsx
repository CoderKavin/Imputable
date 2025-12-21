"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Search, FileText, Loader2, X } from "lucide-react";
import { useAuth, useOrganization } from "@clerk/nextjs";
import { cn } from "@/lib/utils";

interface SearchResult {
  id: string;
  decision_number: number;
  title: string;
  status: string;
  impact_level: string;
  tags: string[];
}

interface SearchCommandProps {
  className?: string;
}

export function SearchCommand({ className }: SearchCommandProps) {
  const router = useRouter();
  const { getToken } = useAuth();
  const { organization } = useOrganization();

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);

  // Handle keyboard shortcut (Cmd+K)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen(true);
      }
      if (e.key === "Escape") {
        setOpen(false);
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Search API call
  const performSearch = useCallback(
    async (searchQuery: string) => {
      if (!searchQuery.trim() || !organization?.id) {
        setResults([]);
        return;
      }

      setLoading(true);
      try {
        const token = await getToken();
        const API_BASE =
          process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

        const response = await fetch(
          `${API_BASE}/decisions?page=1&page_size=10&search=${encodeURIComponent(searchQuery)}`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
              "X-Organization-ID": organization.id,
            },
          },
        );

        if (response.ok) {
          const data = await response.json();
          setResults(data.items || []);
        } else {
          setResults([]);
        }
      } catch (error) {
        console.error("Search error:", error);
        setResults([]);
      } finally {
        setLoading(false);
      }
    },
    [getToken, organization?.id],
  );

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      performSearch(query);
    }, 300);

    return () => clearTimeout(timer);
  }, [query, performSearch]);

  // Handle keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && results[selectedIndex]) {
      e.preventDefault();
      navigateToDecision(results[selectedIndex].id);
    }
  };

  const navigateToDecision = (id: string) => {
    setOpen(false);
    setQuery("");
    router.push(`/decisions/${id}`);
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      draft: "bg-gray-100 text-gray-700",
      pending_review: "bg-amber-100 text-amber-700",
      approved: "bg-green-100 text-green-700",
      deprecated: "bg-red-100 text-red-700",
      superseded: "bg-purple-100 text-purple-700",
    };
    return colors[status] || "bg-gray-100 text-gray-700";
  };

  return (
    <>
      {/* Search Trigger Button */}
      <button
        onClick={() => setOpen(true)}
        className={cn(
          "relative flex items-center gap-2 w-64 px-3 py-2 rounded-2xl",
          "border border-gray-200 bg-white text-sm text-gray-500",
          "hover:border-gray-300 transition-colors",
          className,
        )}
      >
        <Search className="w-4 h-4 text-gray-400" />
        <span>Search decisions...</span>
        <kbd className="absolute right-3 px-1.5 py-0.5 text-[10px] font-mono text-gray-400 bg-gray-100 rounded">
          ⌘K
        </kbd>
      </button>

      {/* Modal Overlay */}
      {open && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[100]"
            onClick={() => setOpen(false)}
          />

          {/* Dialog */}
          <div className="fixed inset-0 z-[101] flex items-start justify-center pt-[15vh] px-4">
            <div className="w-full max-w-xl bg-white rounded-2xl shadow-2xl border border-gray-200 overflow-hidden">
              {/* Search Input */}
              <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-100">
                <Search className="w-5 h-5 text-gray-400" />
                <input
                  type="text"
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    setSelectedIndex(0);
                  }}
                  onKeyDown={handleKeyDown}
                  placeholder="Search decisions by title, tags, or content..."
                  className="flex-1 text-base outline-none placeholder:text-gray-400"
                  autoFocus
                />
                {loading && (
                  <Loader2 className="w-4 h-4 animate-spin text-gray-400" />
                )}
                <button
                  onClick={() => setOpen(false)}
                  className="p-1 rounded-lg hover:bg-gray-100"
                >
                  <X className="w-4 h-4 text-gray-400" />
                </button>
              </div>

              {/* Results */}
              <div className="max-h-80 overflow-y-auto">
                {query && results.length === 0 && !loading && (
                  <div className="px-4 py-8 text-center text-gray-500">
                    <FileText className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>No decisions found for "{query}"</p>
                  </div>
                )}

                {results.length > 0 && (
                  <ul className="py-2">
                    {results.map((result, index) => (
                      <li key={result.id}>
                        <button
                          onClick={() => navigateToDecision(result.id)}
                          onMouseEnter={() => setSelectedIndex(index)}
                          className={cn(
                            "w-full px-4 py-3 flex items-start gap-3 text-left transition-colors",
                            selectedIndex === index
                              ? "bg-indigo-50"
                              : "hover:bg-gray-50",
                          )}
                        >
                          <FileText className="w-5 h-5 text-gray-400 mt-0.5 flex-shrink-0" />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-xs text-gray-500">
                                DEC-{result.decision_number}
                              </span>
                              <span
                                className={cn(
                                  "px-2 py-0.5 rounded-full text-xs font-medium",
                                  getStatusColor(result.status),
                                )}
                              >
                                {result.status.replace("_", " ")}
                              </span>
                            </div>
                            <p className="font-medium text-gray-900 truncate">
                              {result.title}
                            </p>
                            {result.tags.length > 0 && (
                              <div className="flex gap-1 mt-1">
                                {result.tags.slice(0, 3).map((tag) => (
                                  <span
                                    key={tag}
                                    className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded"
                                  >
                                    {tag}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}

                {!query && (
                  <div className="px-4 py-6 text-center text-gray-500">
                    <p className="text-sm">
                      Start typing to search decisions...
                    </p>
                  </div>
                )}
              </div>

              {/* Footer */}
              <div className="px-4 py-2 border-t border-gray-100 bg-gray-50 flex items-center gap-4 text-xs text-gray-500">
                <span className="flex items-center gap-1">
                  <kbd className="px-1.5 py-0.5 bg-white border border-gray-200 rounded">
                    ↑
                  </kbd>
                  <kbd className="px-1.5 py-0.5 bg-white border border-gray-200 rounded">
                    ↓
                  </kbd>
                  to navigate
                </span>
                <span className="flex items-center gap-1">
                  <kbd className="px-1.5 py-0.5 bg-white border border-gray-200 rounded">
                    ↵
                  </kbd>
                  to select
                </span>
                <span className="flex items-center gap-1">
                  <kbd className="px-1.5 py-0.5 bg-white border border-gray-200 rounded">
                    esc
                  </kbd>
                  to close
                </span>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
}
