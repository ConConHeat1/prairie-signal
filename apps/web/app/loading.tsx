export default function Loading() {
  return (
    <main
      aria-busy="true"
      aria-label="Loading Prairie Signal"
      className="route-loading"
    >
      <div className="route-loading__mark" />
      <span>Preparing your forecast…</span>
    </main>
  );
}
