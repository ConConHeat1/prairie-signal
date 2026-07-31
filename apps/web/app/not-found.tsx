import Link from "next/link";

export default function NotFound() {
  return (
    <main className="route-error">
      <p className="eyebrow">404 · Off the map</p>
      <h1>That page isn’t part of this forecast.</h1>
      <p>Prairie Signal currently provides one focused weather view.</p>
      <Link className="ps-button ps-button--primary" href="/">
        Return to the forecast
      </Link>
    </main>
  );
}
