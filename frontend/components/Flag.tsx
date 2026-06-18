// Country flag icon (authentic ESPN flag images). Plain <img> so external URLs
// need no next/image domain config. Falls back to a neutral dot if missing.
export function Flag({
  src,
  name,
  size = 18,
}: {
  src?: string | null;
  name?: string;
  size?: number;
}) {
  if (!src) {
    return (
      <span
        className="inline-block shrink-0 rounded-sm bg-pitch-edge"
        style={{ width: size, height: size }}
        aria-hidden
      />
    );
  }
  return (
    <img
      src={src}
      alt={name ? `${name} flag` : ""}
      width={size}
      height={size}
      loading="lazy"
      className="inline-block shrink-0 rounded-sm object-contain"
      style={{ width: size, height: size }}
    />
  );
}

// Flag + team name inline, the common pattern across pages.
export function TeamLabel({
  name,
  flag,
  size = 18,
  className = "",
}: {
  name: string;
  flag?: string | null;
  size?: number;
  className?: string;
}) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <Flag src={flag} name={name} size={size} />
      <span>{name}</span>
    </span>
  );
}
