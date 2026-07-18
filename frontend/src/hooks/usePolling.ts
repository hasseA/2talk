import { useEffect } from "react"

export function usePolling(
  task: () => Promise<void>,
  enabled: boolean,
  intervalMs = 2000,
): void {
  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined

    const run = async () => {
      await task().catch(() => undefined)
      if (!cancelled) timer = setTimeout(run, intervalMs)
    }
    void run()
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [enabled, intervalMs, task])
}
