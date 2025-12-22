"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { useOrganization } from "@/contexts/OrganizationContext";
import {
  Bell,
  FileText,
  AlertTriangle,
  CheckCircle2,
  Clock,
  X,
  Loader2,
  RefreshCw,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatRelativeTime } from "@/lib/utils";

interface Notification {
  id: string;
  type:
    | "decision_created"
    | "decision_updated"
    | "review_needed"
    | "approved"
    | "expired";
  title: string;
  message: string;
  decision_id?: string;
  decision_number?: number;
  created_at: string;
  read: boolean;
}

export function NotificationsDropdown() {
  const router = useRouter();
  const { getToken } = useAuth();
  const { currentOrganization } = useOrganization();
  const dropdownRef = useRef<HTMLDivElement>(null);

  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Fetch notifications (simulated for now - would connect to real API)
  const fetchNotifications = async () => {
    if (!currentOrganization?.id) return;

    setLoading(true);
    try {
      const token = await getToken();
      const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

      // Try to fetch from risk dashboard update requests as notifications
      const response = await fetch(
        `${API_BASE}/api/v1/risk-dashboard/update-requests?my_decisions_only=false`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            "X-Organization-ID": currentOrganization.id,
          },
        },
      );

      if (response.ok) {
        const data = await response.json();
        // Transform update requests into notifications
        const notifs: Notification[] = (data || [])
          .slice(0, 10)
          .map((req: any) => ({
            id: req.id,
            type: "review_needed" as const,
            title: `Review requested for DEC-${req.decision_number || "?"}`,
            message:
              req.message ||
              "A team member has requested you review this decision.",
            decision_id: req.decision_id,
            decision_number: req.decision_number,
            created_at: req.created_at,
            read: false,
          }));
        setNotifications(notifs);
        setUnreadCount(notifs.filter((n) => !n.read).length);
      } else if (response.status === 402) {
        // Pro feature - show empty state
        setNotifications([]);
        setUnreadCount(0);
      }
    } catch (error) {
      console.error("Failed to fetch notifications:", error);
      // On error, show empty notifications (not an error state)
      setNotifications([]);
    } finally {
      setLoading(false);
    }
  };

  // Fetch on mount and when org changes
  useEffect(() => {
    if (currentOrganization?.id) {
      fetchNotifications();
    }
  }, [currentOrganization?.id]);

  // Refresh when dropdown opens
  useEffect(() => {
    if (open && currentOrganization?.id) {
      fetchNotifications();
    }
  }, [open]);

  const getIcon = (type: Notification["type"]) => {
    switch (type) {
      case "decision_created":
        return <FileText className="w-4 h-4 text-blue-500" />;
      case "decision_updated":
        return <RefreshCw className="w-4 h-4 text-indigo-500" />;
      case "review_needed":
        return <Clock className="w-4 h-4 text-amber-500" />;
      case "approved":
        return <CheckCircle2 className="w-4 h-4 text-green-500" />;
      case "expired":
        return <AlertTriangle className="w-4 h-4 text-red-500" />;
      default:
        return <Bell className="w-4 h-4 text-gray-500" />;
    }
  };

  const handleNotificationClick = (notification: Notification) => {
    // Mark as read (in a real app, would call API)
    setNotifications((prev) =>
      prev.map((n) => (n.id === notification.id ? { ...n, read: true } : n)),
    );
    setUnreadCount((prev) => Math.max(0, prev - 1));

    // Navigate to decision if available
    if (notification.decision_id) {
      setOpen(false);
      router.push(`/decisions/${notification.decision_id}`);
    }
  };

  const markAllRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    setUnreadCount(0);
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Bell Button */}
      <button
        onClick={() => setOpen(!open)}
        className="relative p-2 rounded-xl hover:bg-gray-100 transition-colors"
      >
        <Bell className="w-5 h-5 text-gray-500" />
        {unreadCount > 0 && (
          <span className="absolute top-1 right-1 min-w-[18px] h-[18px] flex items-center justify-center px-1 text-[10px] font-bold text-white bg-red-500 rounded-full">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute right-0 mt-2 w-96 bg-white rounded-2xl shadow-xl border border-gray-200 overflow-hidden z-50">
          {/* Header */}
          <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
            <h3 className="font-semibold text-gray-900">Notifications</h3>
            <div className="flex items-center gap-2">
              {unreadCount > 0 && (
                <button
                  onClick={markAllRead}
                  className="text-xs text-indigo-600 hover:text-indigo-700 font-medium"
                >
                  Mark all read
                </button>
              )}
              <button
                onClick={() => setOpen(false)}
                className="p-1 rounded-lg hover:bg-gray-100"
              >
                <X className="w-4 h-4 text-gray-400" />
              </button>
            </div>
          </div>

          {/* Content */}
          <div className="max-h-96 overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
              </div>
            ) : notifications.length === 0 ? (
              <div className="py-8 text-center">
                <Bell className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                <p className="text-sm text-gray-500">No notifications yet</p>
                <p className="text-xs text-gray-400 mt-1">
                  You&apos;ll see updates about your decisions here
                </p>
              </div>
            ) : (
              <ul className="divide-y divide-gray-100">
                {notifications.map((notification) => (
                  <li key={notification.id}>
                    <button
                      onClick={() => handleNotificationClick(notification)}
                      className={cn(
                        "w-full px-4 py-3 flex items-start gap-3 text-left hover:bg-gray-50 transition-colors",
                        !notification.read && "bg-indigo-50/50",
                      )}
                    >
                      <div className="mt-0.5">{getIcon(notification.type)}</div>
                      <div className="flex-1 min-w-0">
                        <p
                          className={cn(
                            "text-sm",
                            notification.read
                              ? "text-gray-700"
                              : "text-gray-900 font-medium",
                          )}
                        >
                          {notification.title}
                        </p>
                        <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">
                          {notification.message}
                        </p>
                        <p className="text-xs text-gray-400 mt-1">
                          {formatRelativeTime(notification.created_at)}
                        </p>
                      </div>
                      {!notification.read && (
                        <div className="w-2 h-2 rounded-full bg-indigo-500 mt-2" />
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Footer */}
          {notifications.length > 0 && (
            <div className="px-4 py-2 border-t border-gray-100 bg-gray-50">
              <button
                onClick={() => {
                  setOpen(false);
                  router.push("/settings");
                }}
                className="text-xs text-gray-500 hover:text-gray-700"
              >
                Notification settings →
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
