"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  FileText,
  Loader2,
  X,
  Plus,
  Clock,
  ArrowRight,
  Hash,
  Tag,
  Zap,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  History,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useOrganization } from "@/contexts/OrganizationContext";
import { cn } from "@/lib/utils";

interface SearchResult {
  id: string;
  decision_number: number;
  title: string;
  status: string;
  impact_level: string;
  tags: string[];
  created_at?: string;
}

interface QuickAction {
  id: string;
  label: string;
  description: string;
  icon: React.ReactNode;
  action: () => void;
  shortcut?: string;
}

interface SearchCommandProps {
  className?: string;
}

export function SearchCommand({ className }: SearchCommandProps) {
  const router = useRouter();
  const { getToken } = useAuth();
  const { currentOrganization } = useOrganization();
  const inputRef = useRef<HTMLInputElement>(null);

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [recentSearches, setRecentSearches] = useState<string[]>([]);
  const [recentDecisions, setRecentDecisions] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [activeSection, setActiveSection] = useState<
    "actions" | "results" | "recent"
  >("actions");

  // Quick actions for power users
  const quickActions: QuickAction[] = [
    {
      id: "new-decision",
      label: "Create New Decision",
      description: "Document a new engineering decision",
      icon: <Plus className="w-4 h-4" />,
      action: () => {
        setOpen(false);
        router.push("/decisions/new");
      },
      shortcut: "N",
    },
    {
      id: "view-decisions",
      label: "View All Decisions",
      description: "Browse your decision catalog",
      icon: <FileText className="w-4 h-4" />,
      action: () => {
        setOpen(false);
        router.push("/decisions");
      },
      shortcut: "D",
    },
    {
      id: "pending-review",
      label: "Pending Reviews",
      description: "Decisions awaiting your approval",
      icon: <Clock className="w-4 h-4" />,
      action: () => {
        setOpen(false);
        router.push("/decisions?status=pending_review");
      },
      shortcut: "P",
    },
    {
      id: "at-risk",
      label: "At-Risk Decisions",
      description: "Decisions needing attention",
      icon: <AlertTriangle className="w-4 h-4" />,
      action: () => {
        setOpen(false);
        router.push("/decisions?status=at_risk");
      },
      shortcut: "R",
    },
    {
      id: "audit-export",
      label: "Generate Audit Report",
      description: "Export compliance documentation",
      icon: <TrendingUp className="w-4 h-4" />,
      action: () => {
        setOpen(false);
        router.push("/audit");
      },
      shortcut: "A",
    },
  ];

  // Load recent searches from localStorage
  useEffect(() => {
    const stored = localStorage.getItem("imputable_recent_searches");
    if (stored) {
      try {
        setRecentSearches(JSON.parse(stored).slice(0, 5));
      } catch {
        // Ignore parse errors
      }
    }
  }, []);

  // Save search to recent
  const saveRecentSearch = useCallback((searchTerm: string) => {
    if (!searchTerm.trim()) return;
    setRecentSearches((prev) => {
      const updated = [
        searchTerm,
        ...prev.filter((s) => s !== searchTerm),
      ].slice(0, 5);
      localStorage.setItem(
        "imputable_recent_searches",
        JSON.stringify(updated),
      );
      return updated;
    });
  }, []);

  // Handle keyboard shortcuts - both global and when search is open
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger shortcuts when typing in inputs/textareas (except for specific keys)
      const target = e.target as HTMLElement;
      const isTyping =
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable;

      // Open search with Cmd+K (always works)
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen(true);
        return;
      }

      // Escape closes the search
      if (e.key === "Escape") {
        if (open) {
          setOpen(false);
          setQuery("");
        }
        return;
      }

      // Show help with ? (when not typing)
      if (e.key === "?" && !isTyping && !open) {
        e.preventDefault();
        router.push("/help");
        return;
      }

      // Global shortcuts with Cmd/Ctrl (work both when search is open and closed)
      if (e.metaKey || e.ctrlKey) {
        const action = quickActions.find(
          (a) => a.shortcut?.toLowerCase() === e.key.toLowerCase(),
        );
        if (action) {
          // Cmd+N for new decision should always work (unless typing in input)
          if (e.key.toLowerCase() === "n" && isTyping) {
            return; // Allow default browser behavior in inputs
          }
          e.preventDefault();
          action.action();
          return;
        }
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, quickActions, router]);

  // Focus input when modal opens
  useEffect(() => {
    if (open && inputRef.current) {
      inputRef.current.focus();
    }
  }, [open]);

  // Reset selection when query changes
  useEffect(() => {
    setSelectedIndex(0);
    if (query) {
      setActiveSection("results");
    } else {
      setActiveSection("actions");
    }
  }, [query]);

  // Search API call
  const performSearch = useCallback(
    async (searchQuery: string) => {
      if (!searchQuery.trim() || !currentOrganization?.id) {
        setResults([]);
        return;
      }

      setLoading(true);
      try {
        const token = await getToken();
        const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

        const response = await fetch(
          `${API_BASE}/api/v1/decisions?page=1&page_size=10&search=${encodeURIComponent(searchQuery)}`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
              "X-Organization-ID": currentOrganization.id,
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
    [getToken, currentOrganization?.id],
  );

  // Fetch recent decisions on mount
  useEffect(() => {
    if (!open) return;

    const abortController = new AbortController();

    const fetchRecent = async () => {
      if (!currentOrganization?.id) return;
      try {
        const token = await getToken();
        const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
        const response = await fetch(
          `${API_BASE}/api/v1/decisions?page=1&page_size=5`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
              "X-Organization-ID": currentOrganization.id,
            },
            signal: abortController.signal,
          },
        );
        if (response.ok) {
          const data = await response.json();
          setRecentDecisions(data.items || []);
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        // Ignore other errors for recent fetch
      }
    };

    fetchRecent();

    return () => abortController.abort();
  }, [open, currentOrganization?.id, getToken]);

  // Debounced search
  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      return;
    }

    const timer = setTimeout(() => {
      performSearch(query);
    }, 200);

    return () => clearTimeout(timer);
  }, [query, performSearch]);

  // Calculate total items for navigation
  const getTotalItems = () => {
    if (query) {
      return results.length;
    }
    return quickActions.length + recentDecisions.length;
  };

  // Handle keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    const totalItems = getTotalItems();

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, totalItems - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      handleSelect();
    } else if (e.key === "Tab") {
      e.preventDefault();
      // Cycle through sections
      if (!query) {
        setActiveSection((prev) => (prev === "actions" ? "recent" : "actions"));
        setSelectedIndex(0);
      }
    }
  };

  const handleSelect = () => {
    if (query && results[selectedIndex]) {
      saveRecentSearch(query);
      navigateToDecision(results[selectedIndex].id);
    } else if (!query) {
      if (selectedIndex < quickActions.length) {
        quickActions[selectedIndex].action();
      } else {
        const recentIndex = selectedIndex - quickActions.length;
        if (recentDecisions[recentIndex]) {
          navigateToDecision(recentDecisions[recentIndex].id);
        }
      }
    }
  };

  const navigateToDecision = (id: string) => {
    setOpen(false);
    setQuery("");
    router.push(`/decisions/${id}`);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "approved":
        return <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />;
      case "pending_review":
        return <Clock className="w-3.5 h-3.5 text-amber-500" />;
      case "deprecated":
        return <AlertTriangle className="w-3.5 h-3.5 text-red-500" />;
      default:
        return <FileText className="w-3.5 h-3.5 text-gray-400" />;
    }
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      draft: "bg-gray-100 text-gray-700",
      pending_review: "bg-amber-100 text-amber-700",
      approved: "bg-emerald-100 text-emerald-700",
      deprecated: "bg-red-100 text-red-700",
      superseded: "bg-purple-100 text-purple-700",
    };
    return colors[status] || "bg-gray-100 text-gray-700";
  };

  const getImpactColor = (impact: string) => {
    const colors: Record<string, string> = {
      critical: "text-red-600",
      high: "text-orange-600",
      medium: "text-amber-600",
      low: "text-green-600",
    };
    return colors[impact] || "text-gray-600";
  };

  return (
    <>
      {/* Search Trigger Button */}
      <button
        onClick={() => setOpen(true)}
        className={cn(
          "relative flex items-center gap-2 w-64 px-3 py-2 rounded-xl",
          "border border-gray-200 bg-white text-sm text-gray-500",
          "hover:border-gray-300 hover:bg-gray-50 transition-all duration-200",
          "focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-300",
          className,
        )}
      >
        <Search className="w-4 h-4 text-gray-400" />
        <span className="flex-1 text-left">Search decisions...</span>
        <kbd className="px-1.5 py-0.5 text-[10px] font-mono text-gray-400 bg-gray-100 rounded border border-gray-200">
          ⌘K
        </kbd>
      </button>

      {/* Modal Overlay */}
      {open && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/50 z-[200] animate-in fade-in duration-200"
            onClick={() => {
              setOpen(false);
              setQuery("");
            }}
          />

          {/* Dialog */}
          <div className="fixed inset-0 z-[201] flex items-start justify-center pt-[12vh] px-4">
            <div className="w-full max-w-2xl bg-white rounded-2xl shadow-2xl border border-gray-200 overflow-hidden animate-in slide-in-from-top-4 duration-300">
              {/* Search Input */}
              <div className="flex items-center gap-3 px-5 py-4 border-b border-gray-100">
                <Search className="w-5 h-5 text-indigo-500" />
                <input
                  ref={inputRef}
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Search decisions, or type a command..."
                  className="flex-1 text-base outline-none placeholder:text-gray-400 bg-transparent"
                  autoFocus
                />
                {loading && (
                  <Loader2 className="w-5 h-5 animate-spin text-indigo-500" />
                )}
                {query && !loading && (
                  <button
                    onClick={() => setQuery("")}
                    className="p-1 rounded-lg hover:bg-gray-100 transition-colors"
                  >
                    <X className="w-4 h-4 text-gray-400" />
                  </button>
                )}
                <button
                  onClick={() => {
                    setOpen(false);
                    setQuery("");
                  }}
                  className="px-2 py-1 text-xs font-medium text-gray-500 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
                >
                  ESC
                </button>
              </div>

              {/* Results Area */}
              <div className="max-h-[60vh] overflow-y-auto">
                {/* Search Results */}
                {query && (
                  <div className="py-2">
                    {loading ? (
                      <div className="px-5 py-8 text-center">
                        <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mx-auto mb-3" />
                        <p className="text-sm text-gray-500">
                          Searching decisions...
                        </p>
                      </div>
                    ) : results.length === 0 ? (
                      <div className="px-5 py-8 text-center">
                        <Search className="w-10 h-10 mx-auto mb-3 text-gray-300" />
                        <p className="text-sm font-medium text-gray-900 mb-1">
                          No decisions found
                        </p>
                        <p className="text-xs text-gray-500 mb-4">
                          Try a different search term or create a new decision
                        </p>
                        <button
                          onClick={() => {
                            setOpen(false);
                            router.push("/decisions/new");
                          }}
                          className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-xl hover:bg-indigo-700 transition-colors"
                        >
                          <Plus className="w-4 h-4" />
                          Create Decision
                        </button>
                      </div>
                    ) : (
                      <>
                        <div className="px-5 py-2">
                          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                            {results.length} result
                            {results.length !== 1 ? "s" : ""}
                          </p>
                        </div>
                        <ul>
                          {results.map((result, index) => (
                            <li key={result.id}>
                              <button
                                onClick={() => {
                                  saveRecentSearch(query);
                                  navigateToDecision(result.id);
                                }}
                                onMouseEnter={() => setSelectedIndex(index)}
                                className={cn(
                                  "w-full px-5 py-3 flex items-start gap-4 text-left transition-all duration-150",
                                  selectedIndex === index
                                    ? "bg-indigo-50 border-l-2 border-indigo-500"
                                    : "hover:bg-gray-50 border-l-2 border-transparent",
                                )}
                              >
                                <div className="mt-1">
                                  {getStatusIcon(result.status)}
                                </div>
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2 mb-1">
                                    <span className="font-mono text-xs text-indigo-600 font-medium">
                                      DEC-{result.decision_number}
                                    </span>
                                    <span
                                      className={cn(
                                        "px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide",
                                        getStatusColor(result.status),
                                      )}
                                    >
                                      {result.status.replace("_", " ")}
                                    </span>
                                    {result.impact_level && (
                                      <span
                                        className={cn(
                                          "text-[10px] font-semibold uppercase",
                                          getImpactColor(result.impact_level),
                                        )}
                                      >
                                        {result.impact_level}
                                      </span>
                                    )}
                                  </div>
                                  <p className="font-medium text-gray-900 truncate">
                                    {result.title}
                                  </p>
                                  {result.tags && result.tags.length > 0 && (
                                    <div className="flex items-center gap-1.5 mt-1.5">
                                      <Tag className="w-3 h-3 text-gray-400" />
                                      {result.tags.slice(0, 3).map((tag) => (
                                        <span
                                          key={tag}
                                          className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-md"
                                        >
                                          {tag}
                                        </span>
                                      ))}
                                      {result.tags.length > 3 && (
                                        <span className="text-xs text-gray-400">
                                          +{result.tags.length - 3}
                                        </span>
                                      )}
                                    </div>
                                  )}
                                </div>
                                <ArrowRight
                                  className={cn(
                                    "w-4 h-4 mt-1 transition-all",
                                    selectedIndex === index
                                      ? "text-indigo-500 translate-x-0 opacity-100"
                                      : "text-gray-300 -translate-x-2 opacity-0",
                                  )}
                                />
                              </button>
                            </li>
                          ))}
                        </ul>
                      </>
                    )}
                  </div>
                )}

                {/* Quick Actions (when no query) */}
                {!query && (
                  <>
                    {/* Quick Actions */}
                    <div className="py-2 border-b border-gray-100">
                      <div className="px-5 py-2">
                        <p className="text-xs font-medium text-gray-500 uppercase tracking-wider flex items-center gap-2">
                          <Zap className="w-3.5 h-3.5" />
                          Quick Actions
                        </p>
                      </div>
                      <ul>
                        {quickActions.map((action, index) => (
                          <li key={action.id}>
                            <button
                              onClick={action.action}
                              onMouseEnter={() => setSelectedIndex(index)}
                              className={cn(
                                "w-full px-5 py-2.5 flex items-center gap-3 text-left transition-all duration-150",
                                selectedIndex === index &&
                                  activeSection === "actions"
                                  ? "bg-indigo-50"
                                  : "hover:bg-gray-50",
                              )}
                            >
                              <div
                                className={cn(
                                  "w-8 h-8 rounded-lg flex items-center justify-center transition-colors",
                                  selectedIndex === index &&
                                    activeSection === "actions"
                                    ? "bg-indigo-100 text-indigo-600"
                                    : "bg-gray-100 text-gray-500",
                                )}
                              >
                                {action.icon}
                              </div>
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-gray-900">
                                  {action.label}
                                </p>
                                <p className="text-xs text-gray-500">
                                  {action.description}
                                </p>
                              </div>
                              {action.shortcut && (
                                <kbd className="px-2 py-1 text-[10px] font-mono text-gray-400 bg-gray-100 rounded border border-gray-200">
                                  ⌘{action.shortcut}
                                </kbd>
                              )}
                            </button>
                          </li>
                        ))}
                      </ul>
                    </div>

                    {/* Recent Decisions */}
                    {recentDecisions.length > 0 && (
                      <div className="py-2">
                        <div className="px-5 py-2">
                          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider flex items-center gap-2">
                            <History className="w-3.5 h-3.5" />
                            Recent Decisions
                          </p>
                        </div>
                        <ul>
                          {recentDecisions.map((decision, index) => {
                            const adjustedIndex = quickActions.length + index;
                            return (
                              <li key={decision.id}>
                                <button
                                  onClick={() =>
                                    navigateToDecision(decision.id)
                                  }
                                  onMouseEnter={() =>
                                    setSelectedIndex(adjustedIndex)
                                  }
                                  className={cn(
                                    "w-full px-5 py-2.5 flex items-center gap-3 text-left transition-all duration-150",
                                    selectedIndex === adjustedIndex
                                      ? "bg-indigo-50"
                                      : "hover:bg-gray-50",
                                  )}
                                >
                                  <div className="w-8 h-8 rounded-lg bg-gray-100 flex items-center justify-center">
                                    {getStatusIcon(decision.status)}
                                  </div>
                                  <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2">
                                      <span className="font-mono text-xs text-gray-500">
                                        DEC-{decision.decision_number}
                                      </span>
                                      <span
                                        className={cn(
                                          "px-1.5 py-0.5 rounded text-[10px] font-medium",
                                          getStatusColor(decision.status),
                                        )}
                                      >
                                        {decision.status.replace("_", " ")}
                                      </span>
                                    </div>
                                    <p className="text-sm text-gray-900 truncate">
                                      {decision.title}
                                    </p>
                                  </div>
                                  <ArrowRight className="w-4 h-4 text-gray-300" />
                                </button>
                              </li>
                            );
                          })}
                        </ul>
                      </div>
                    )}

                    {/* Recent Searches */}
                    {recentSearches.length > 0 && (
                      <div className="py-2 border-t border-gray-100">
                        <div className="px-5 py-2">
                          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider flex items-center gap-2">
                            <Clock className="w-3.5 h-3.5" />
                            Recent Searches
                          </p>
                        </div>
                        <div className="px-5 flex flex-wrap gap-2">
                          {recentSearches.map((search) => (
                            <button
                              key={search}
                              onClick={() => setQuery(search)}
                              className="px-3 py-1.5 text-xs text-gray-600 bg-gray-100 rounded-full hover:bg-gray-200 transition-colors"
                            >
                              {search}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>

              {/* Footer */}
              <div className="px-5 py-3 border-t border-gray-100 bg-gray-50/80 flex items-center justify-between text-xs text-gray-500">
                <div className="flex items-center gap-4">
                  <span className="flex items-center gap-1.5">
                    <kbd className="px-1.5 py-0.5 bg-white border border-gray-200 rounded text-[10px] font-mono">
                      ↑↓
                    </kbd>
                    navigate
                  </span>
                  <span className="flex items-center gap-1.5">
                    <kbd className="px-1.5 py-0.5 bg-white border border-gray-200 rounded text-[10px] font-mono">
                      ↵
                    </kbd>
                    select
                  </span>
                  <span className="flex items-center gap-1.5">
                    <kbd className="px-1.5 py-0.5 bg-white border border-gray-200 rounded text-[10px] font-mono">
                      esc
                    </kbd>
                    close
                  </span>
                </div>
                <div className="flex items-center gap-1 text-gray-400">
                  <Zap className="w-3 h-3" />
                  <span>Powered by Imputable</span>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
}
