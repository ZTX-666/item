import { eq } from 'drizzle-orm';
import { getDb } from '../db/index.js';
import { projects, budgetLines, scheduleTasks } from '../db/schema.js';

export async function getProjectSummary(projectId: string) {
  const db = getDb();
  const [project] = await db.select().from(projects).where(eq(projects.id, projectId)).limit(1);
  if (!project) return { error: 'Project not found' };

  const budget = await db.select().from(budgetLines).where(eq(budgetLines.projectId, projectId));
  const schedule = await db.select().from(scheduleTasks).where(eq(scheduleTasks.projectId, projectId));

  const totalBudget = budget.reduce((s, b) => s + Number(b.originalBudget || 0) + Number(b.approvedChanges || 0), 0);
  const totalSpent = budget.reduce((s, b) => s + Number(b.actualCosts || 0), 0);
  const avgProgress = schedule.length > 0
    ? schedule.reduce((s, t) => s + Number(t.percentComplete || 0), 0) / schedule.length
    : 0;

  return {
    id: project.id,
    name: project.name,
    project_number: project.projectNumber,
    status: project.status,
    contract_amount: project.contractAmount,
    budget_health: {
      total: totalBudget,
      spent: totalSpent,
      percent_consumed: totalBudget > 0 ? Math.round((totalSpent / totalBudget) * 100) : 0,
    },
    schedule_health: {
      percent_complete: Math.round(avgProgress * 100) / 100,
      estimated_completion: project.estimatedCompletion,
    },
    key_personnel: {
      owner: project.ownerName,
      architect: project.architectName,
      superintendent: project.superintendent,
      project_manager: project.projectManager,
    },
  };
}
