export function SkeletonCard({ className = "" }: { className?: string }) {
  return (
    <div className={`card p-3 ${className}`}>
      <div className="skel-block h-3 w-16" />
      <div className="skel-block mt-2 h-7 w-12" />
    </div>
  );
}

export function SkeletonStatStrip() {
  return (
    <div className="card p-4">
      <div className="skel-block h-3 w-24" />
      <div className="skel-block mt-3 h-8 w-14" />
    </div>
  );
}
