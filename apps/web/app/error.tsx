"use client";

import { Button } from "@prairie-signal/ui";
import { useEffect } from "react";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Next.js captures the detailed exception server-side; avoid logging location-bearing URLs here.
    void error.digest;
  }, [error]);

  return (
    <main className="route-error">
      <p className="eyebrow">Prairie Signal</p>
      <h1>The forecast view couldn’t start.</h1>
      <p>Your location was not saved. Try loading the page again.</p>
      <Button onClick={reset}>Try again</Button>
    </main>
  );
}
