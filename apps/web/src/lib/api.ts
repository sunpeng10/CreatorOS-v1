"use client";
import { useCallback, useEffect, useState } from "react";
import { errorMessage } from "./format";
export type Row = { id: string; [key: string]: any };
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function api<T = any>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const form = options.body instanceof FormData;
  const response = await fetch(`/api${path}`, {
    ...options,
    credentials: "same-origin",
    headers: {
      ...(!form && options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(errorMessage(payload), response.status);
  return payload as T;
}
export function post<T = any>(path: string, body?: unknown, method = "POST") {
  return api<T>(path, {
    method,
    body: body instanceof FormData ? body : JSON.stringify(body ?? {}),
  });
}
export function rows(data: any): Row[] {
  return Array.isArray(data)
    ? data
    : Array.isArray(data?.items)
      ? data.items
      : [];
}
export function useResource<T = any>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(!!path);
  const refresh = useCallback(async () => {
    if (!path) return;
    setLoading(true);
    setError("");
    try {
      setData(await api<T>(path));
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [path]);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  return { data, error, loading, refresh };
}
