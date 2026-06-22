import { onBeforeUnmount, ref } from 'vue'
import { getJob } from '../services/chitungApi'
import type { JobRun } from '../types/domain'

export function useJobPolling() {
  const activeJob = ref<JobRun | null>(null)
  const jobError = ref('')
  let timer: number | undefined

  function stop() {
    if (timer) {
      window.clearTimeout(timer)
      timer = undefined
    }
  }

  async function poll(jobId: string, onDone?: (job: JobRun) => void | Promise<void>) {
    stop()
    jobError.value = ''
    try {
      const job = await getJob(jobId)
      activeJob.value = job
      if (['success', 'failed'].includes(job.status)) {
        if (job.status === 'failed') jobError.value = job.error || '后台任务执行失败'
        await onDone?.(job)
        return
      }
      timer = window.setTimeout(() => poll(jobId, onDone), 1500)
    } catch (err) {
      jobError.value = err instanceof Error ? err.message : String(err)
    }
  }

  onBeforeUnmount(stop)

  return {
    activeJob,
    jobError,
    poll,
    stop,
  }
}
