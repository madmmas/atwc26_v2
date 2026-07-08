const SKEL = "rounded bg-pitch-edge/70 animate-[skel-pulse_1.2s_ease-in-out_infinite]";

export function SkeletonRow() {
  return (
    <tr className="skeleton-row border-b border-pitch-edge/40">
      <td className="px-4 py-3">
        <div className={`${SKEL} h-4 w-6`} />
      </td>
      <td className="px-4 py-3">
        <div className={`${SKEL} h-4 w-40`} />
      </td>
      <td className="px-4 py-3">
        <div className={`${SKEL} h-4 w-24`} />
      </td>
      <td className="px-4 py-3">
        <div className={`${SKEL} h-5 w-12 rounded-full`} />
      </td>
      {Array.from({ length: 8 }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className={`${SKEL} ml-auto h-4 w-10`} />
        </td>
      ))}
    </tr>
  );
}
