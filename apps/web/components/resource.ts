export interface ResourceState<T> {
  status: "idle" | "loading" | "ready" | "error";
  data: T | null;
  error: string | null;
}

export function loadingResource<T>(): ResourceState<T> {
  return { status: "loading", data: null, error: null };
}
