import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "border-transparent bg-gray-900 text-white",
        secondary: "border-gray-200 bg-gray-50 text-gray-600",
        destructive: "border-red-200 bg-red-50 text-red-700",
        outline: "border-gray-200 text-gray-600",
        // Status variants - Subtle palettes
        draft: "border-gray-200 bg-gray-50 text-gray-600",
        pending_review: "border-amber-200 bg-amber-50 text-amber-700",
        approved: "border-emerald-200 bg-emerald-50 text-emerald-700",
        deprecated: "border-gray-200 bg-gray-50 text-gray-500",
        superseded: "border-purple-200 bg-purple-50 text-purple-600",
        at_risk: "border-red-200 bg-red-50 text-red-700",
        // Impact variants - Subtle palettes
        low: "border-blue-200 bg-blue-50 text-blue-600",
        medium: "border-amber-200 bg-amber-50 text-amber-600",
        high: "border-orange-200 bg-orange-50 text-orange-600",
        critical: "border-red-200 bg-red-50 text-red-700",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
