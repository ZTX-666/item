import { eq, and, lt } from 'drizzle-orm';
import { getDb } from '../db/index.js';
import { rfis, projects } from '../db/schema.js';

export async function getRfiSnapshot(projectId: string) {
  const db = getDb();
  const [project] = await db.select().from(projects).where(eq(projects.id, projectId)).limit(1);
  if (!project) return { error: 'Project not found' };

  const allRfis = await db.select().from(rfis).where(eq(rfis.projectId, projectId));

  const today = new Date().toISOString().split('T')[0];
  const open = allRfis.filter((r) => ['draft', 'open'].includes(r.status));
  const overdue = open.filter((r) => r.dueDate && r.dueDate < today);

  const answered = allRfis.filter((r) => r.respondedAt && r.createdAt);
  const avgResponseDays = answered.length > 0
    ? answered.reduce((s, r) => {
        const created = new Date(r.createdAt!).getTime();
        const responded = new Date(r.respondedAt!).getTime();
        return s + (responded - created) / 86400000;
      }, 0) / answered.length
    : 0;

  return {
    project: { id: project.id, name: project.name },
    total: allRfis.length,
    open: open.length,
    overdue: overdue.length,
    answered: allRfis.filter((r) => r.status === 'answered').length,
    closed: allRfis.filter((r) => r.status === 'closed').length,
    avg_response_days: Math.round(avgResponseDays * 10) / 10,
    by_priority: {
      urgent: allRfis.filter((r) => r.priority === 'urgent').length,
      high: allRfis.filter((r) => r.priority === 'high').length,
      normal: allRfis.filter((r) => r.priority === 'normal').length,
      low: allRfis.filter((r) => r.priority === 'low').length,
    },
  };
}
