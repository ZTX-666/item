import { eq } from 'drizzle-orm';
import { getDb } from '../db/index.js';
import { budgetLines, projects } from '../db/schema.js';

export async function getBudgetSnapshot(projectId: string) {
  const db = getDb();
  const [project] = await db.select().from(projects).where(eq(projects.id, projectId)).limit(1);
  if (!project) return { error: 'Project not found' };

  const budget = await db.select().from(budgetLines).where(eq(budgetLines.projectId, projectId));

  const total = budget.reduce((s, b) => s + Number(b.originalBudget || 0) + Number(b.approvedChanges || 0), 0);
  const spent = budget.reduce((s, b) => s + Number(b.actualCosts || 0), 0);
  const committed = budget.reduce((s, b) => s + Number(b.committedCosts || 0), 0);
  const projected = budget.reduce((s, b) => s + Number(b.estimatedCostAtCompletion || 0), 0);

  return {
    project: { id: project.id, name: project.name },
    total_budget: total,
    spent: spent,
    committed: committed,
    projected_at_completion: projected || spent + committed,
    variance: total - spent,
    percent_consumed: total > 0 ? Math.round((spent / total) * 100) : 0,
    cost_codes: budget.length,
  };
}
