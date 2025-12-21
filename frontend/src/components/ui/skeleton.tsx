import { cn } from "@/lib/utils";

function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-gray-200", className)}
      {...props}
    />
  );
}

function DecisionCardSkeleton() {
  return (
    <div className="border rounded-lg bg-white p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          {/* Header row */}
          <div className="flex items-center gap-2 mb-2">
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-5 w-20 rounded-full" />
            <Skeleton className="h-5 w-16 rounded-full" />
          </div>

          {/* Title */}
          <Skeleton className="h-5 w-3/4 mb-3" />

          {/* Meta row */}
          <div className="flex items-center gap-4">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-4 w-16" />
          </div>

          {/* Tags */}
          <div className="flex items-center gap-1.5 mt-3">
            <Skeleton className="h-5 w-14 rounded-full" />
            <Skeleton className="h-5 w-18 rounded-full" />
            <Skeleton className="h-5 w-12 rounded-full" />
          </div>
        </div>

        <Skeleton className="h-5 w-5 flex-shrink-0" />
      </div>
    </div>
  );
}

function DecisionListSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <DecisionCardSkeleton key={i} />
      ))}
    </div>
  );
}

function UserCardSkeleton() {
  return (
    <div className="w-full p-3 border rounded-lg">
      <div className="flex items-center justify-between">
        <div>
          <Skeleton className="h-5 w-32 mb-2" />
          <Skeleton className="h-4 w-40 mb-1" />
          <Skeleton className="h-3 w-28" />
        </div>
      </div>
    </div>
  );
}

function UserListSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: count }).map((_, i) => (
        <UserCardSkeleton key={i} />
      ))}
    </div>
  );
}

export { Skeleton, DecisionCardSkeleton, DecisionListSkeleton, UserCardSkeleton, UserListSkeleton };
