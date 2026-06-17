/**
 * Shared React Query cache lifetime for presigned-URL queries (image,
 * thumbnail, and model-weights URLs).
 *
 * The API signs GET URLs with a 900s (15 min) TTL, after which the URL 403s.
 * This staleTime MUST stay comfortably below that TTL so React Query refetches
 * a fresh URL before the cached one expires — otherwise images can 403 while
 * still considered fresh. 10 minutes leaves a 5-minute safety margin.
 */
export const PRESIGNED_URL_STALE_MS = 10 * 60 * 1000

/**
 * Garbage-collect cached presigned URLs at the same cadence as their staleness,
 * so stale (already-expired) URLs aren't retained in the cache after refetch.
 */
export const PRESIGNED_URL_GC_MS = PRESIGNED_URL_STALE_MS
