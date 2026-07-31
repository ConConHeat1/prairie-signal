import { type NextRequest, NextResponse } from "next/server";

const SAFE_UPSTREAM_HEADERS = [
  "cache-control",
  "content-type",
  "etag",
  "last-modified",
  "retry-after",
] as const;

interface RouteContext {
  params: Promise<{ path: string[] }>;
}

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  const apiOrigin = (
    process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000"
  ).replace(/\/$/, "");
  const encodedPath = path
    .map((segment) => encodeURIComponent(segment))
    .join("/");
  const upstreamUrl = new URL(`${apiOrigin}/api/v1/${encodedPath}`);
  upstreamUrl.search = request.nextUrl.search;

  try {
    const upstream = await fetch(upstreamUrl, {
      cache: "no-store",
      headers: {
        accept: request.headers.get("accept") ?? "application/json",
      },
      signal: AbortSignal.timeout(15_000),
    });
    const responseHeaders = new Headers();
    for (const header of SAFE_UPSTREAM_HEADERS) {
      const value = upstream.headers.get(header);
      if (value) {
        responseHeaders.set(header, value);
      }
    }
    return new NextResponse(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch {
    return NextResponse.json(
      {
        error: {
          code: "api_unavailable",
          message: "The weather service is temporarily unavailable.",
          retryable: true,
        },
      },
      { status: 503 },
    );
  }
}
