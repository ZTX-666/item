import { eq } from 'drizzle-orm';
import { getDb } from '../db/index.js';
import { scheduleTasks, projects } from '../db/schema.js';

export async function getScheduleSnapshot(projectId: string) {
  const db = getDb();
  const [project] = await db.select().from(projects).where(eq(projects.id, projectId)).limit(1);
  if (!project) return { error: 'Project not found' };

  const tasks = await db.select().from(scheduleTasks).where(eq(scheduleTasks.projectId, projectId));

  const avgProgress = tasks.length > 0
    ? tasks.reduce((s, t) => s + Number(t.percentComplete || 0), 0) / tasks.length
    : 0;

  const today = new Date();
  const estCompletion = project.estimatedCompletion ? new Date(project.estimatedCompletion) : null;
  const daysRemaining = estCompletion ? Math.max(0, Math.ceil((estCompletion.getTime() - today.getTime()) / 86400000)) : null;

  return {
    project: { id: project.id, name: project.name },
    percent_complete: Math.round(avgProgress * 100) / 100,
    days_remaining: daysRemaining,
    estimated_completion: project.estimatedCompletion,
    total_tasks: tasks.length,
    critical_path_tasks: tasks.filter((t) => t.isCriticalPath).length,
    delayed_tasks: tasks.filter((t) => t.status === 'delayed').length,
    by_status: {
      not_started: tasks.filter((t) => t.status === 'not_started').length,
      in_progress: tasks.filter((t) => t.status === 'in_progress').length,
      complete: tasks.filter((t) => t.status === 'complete').length,
      delayed: tasks.filter((t) => t.status === 'delayed').length,
    },
  };
}
