import { cn } from "@/lib/utils";

function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-pulse rounded-xl bg-gray-100", className)}
      {...props}
    />
  );
}

function DecisionCardSkeleton() {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          {/* Decision number */}
          <Skeleton className="h-3 w-16 mb-2" />

          {/* Title */}
          <Skeleton className="h-5 w-3/4 mb-4" />
        </div>

        {/* Status pill */}
        <Skeleton className="h-6 w-20 rounded-full" />
      </div>

      {/* Meta row */}
      <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-50">
        <div className="flex items-center gap-3">
          <Skeleton className="h-6 w-6 rounded-full" />
          <Skeleton className="h-4 w-24" />
        </div>
        <div className="flex items-center gap-3">
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-10" />
        </div>
      </div>

      {/* Tags */}
      <div className="flex items-center gap-2 mt-3">
        <Skeleton className="h-5 w-14 rounded-full" />
        <Skeleton className="h-5 w-18 rounded-full" />
        <Skeleton className="h-5 w-12 rounded-full" />
      </div>
    </div>
  );
}

function DecisionListSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div className="space-y-4">
      {Array.from({ length: count }).map((_, i) => (
        <DecisionCardSkeleton key={i} />
      ))}
    </div>
  );
}

function UserCardSkeleton() {
  return (
    <div className="w-full p-4 bg-gray-50 border border-gray-100 rounded-2xl">
      <div className="flex items-center gap-3">
        <Skeleton className="h-10 w-10 rounded-xl" />
        <div className="flex-1">
          <Skeleton className="h-5 w-32 mb-2" />
          <Skeleton className="h-4 w-40" />
        </div>
      </div>
    </div>
  );
}

function UserListSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <UserCardSkeleton key={i} />
      ))}
    </div>
  );
}

function StatCardSkeleton() {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-6">
      <Skeleton className="h-4 w-24 mb-3" />
      <Skeleton className="h-8 w-16 mb-2" />
      <Skeleton className="h-3 w-20" />
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-8">
      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {Array.from({ length: 4 }).map((_, i) => (
          <StatCardSkeleton key={i} />
        ))}
      </div>

      {/* Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white rounded-3xl border border-gray-100 p-8">
          <Skeleton className="h-6 w-32 mb-6" />
          <div className="grid grid-cols-2 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-24 rounded-2xl" />
            ))}
          </div>
        </div>
        <div className="bg-white rounded-3xl border border-gray-100 p-8">
          <Skeleton className="h-6 w-32 mb-6" />
          <div className="space-y-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="flex items-start gap-3">
                <Skeleton className="h-7 w-7 rounded-full" />
                <div className="flex-1">
                  <Skeleton className="h-4 w-full mb-2" />
                  <Skeleton className="h-3 w-2/3" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export {
  Skeleton,
  DecisionCardSkeleton,
  DecisionListSkeleton,
  UserCardSkeleton,
  UserListSkeleton,
  StatCardSkeleton,
  DashboardSkeleton,
};
