const SKEL = "rounded bg-pitch-edge/70 animate-[skel-pulse_1.2s_ease-in-out_infinite]";

export function SkeletonCard({ className = "" }: { className?: string }) {
  return (
    <div className={`card p-3 ${className}`}>
      <div className={`${SKEL} h-3 w-16`} />
      <div className={`${SKEL} mt-2 h-7 w-12`} />
    </div>
  );
}

export function SkeletonStatStrip() {
  return (
    <div className="card p-4">
      <div className={`${SKEL} h-3 w-24`} />
      <div className={`${SKEL} mt-3 h-8 w-14`} />
    </div>
  );
}
