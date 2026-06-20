import { z } from 'zod';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { eq } from 'drizzle-orm';
import { getDb } from '../db/index.js';
import { estimates, estimateLineItems, rfis, dailyLogs, changeOrders, projects, budgetLines } from '../db/schema.js';

export function registerPrompts(server: McpServer) {
  // ── Estimate Review ──────────────────────────────────────────────────

  server.prompt(
    'estimate-review',
    'Reviews estimate for completeness, missing cost codes, pricing anomalies',
    { estimate_id: z.string().uuid() },
    async (args) => {
      const db = getDb();
      const [estimate] = await db.select().from(estimates).where(eq(estimates.id, args.estimate_id)).limit(1);
      if (!estimate) {
        return { messages: [{ role: 'user' as const, content: { type: 'text' as const, text: 'Estimate not found.' } }] };
      }

      const lineItems = await db.select().from(estimateLineItems).where(eq(estimateLineItems.estimateId, args.estimate_id));

      const context = JSON.stringify({
        estimate: { name: estimate.name, version: estimate.version, status: estimate.status, total: estimate.totalAmount, markup: estimate.markupPercentage, contingency: estimate.contingencyPercentage },
        line_items: lineItems.map((li) => ({ cost_code: li.costCode, description: li.description, quantity: li.quantity, unit: li.unit, unit_cost: li.unitCost, category: li.category })),
      }, null, 2);

      return {
        messages: [
          {
            role: 'user' as const,
            content: {
              type: 'text' as const,
              text: `Review this construction cost estimate for completeness, missing CSI MasterFormat cost codes, pricing anomalies, and recommendations:\n\n${context}\n\nProvide:\n1. Missing cost code divisions\n2. Pricing anomalies (unusually high/low unit costs)\n3. Completeness assessment\n4. Recommendations for improvement`,
            },
          },
        ],
      };
    },
  );

  // ── RFI Draft ────────────────────────────────────────────────────────

  server.prompt(
    'rfi-draft',
    'Drafts RFI response using project context and spec references',
    {
      rfi_id: z.string().uuid(),
      additional_context: z.string().optional(),
    },
    async (args) => {
      const db = getDb();
      const [rfi] = await db.select().from(rfis).where(eq(rfis.id, args.rfi_id)).limit(1);
      if (!rfi) {
        return { messages: [{ role: 'user' as const, content: { type: 'text' as const, text: 'RFI not found.' } }] };
      }

      const [project] = await db.select().from(projects).where(eq(projects.id, rfi.projectId)).limit(1);

      const context = JSON.stringify({
        project: project ? { name: project.name, type: project.projectType } : null,
        rfi: { number: rfi.rfiNumber, subject: rfi.subject, question: rfi.question, priority: rfi.priority, cost_impact: rfi.costImpact, schedule_impact: rfi.scheduleImpact },
        additional_context: args.additional_context,
      }, null, 2);

      return {
        messages: [
          {
            role: 'user' as const,
            content: {
              type: 'text' as const,
              text: `Draft a professional response to this construction RFI:\n\n${context}\n\nProvide:\n1. A clear, detailed response addressing the question\n2. Reference to relevant specifications or standards\n3. Note any cost or schedule implications\n4. Recommended follow-up actions`,
            },
          },
        ],
      };
    },
  );

  // ── Daily Summary ────────────────────────────────────────────────────

  server.prompt(
    'daily-summary',
    'Summarizes daily logs into executive narrative',
    {
      project_id: z.string().uuid(),
      start_date: z.string(),
      end_date: z.string(),
    },
    async (args) => {
      const db = getDb();
      const logs = await db.select().from(dailyLogs)
        .where(eq(dailyLogs.projectId, args.project_id));

      const filteredLogs = logs.filter((l) => l.logDate >= args.start_date && l.logDate <= args.end_date);

      const context = JSON.stringify({
        period: { start: args.start_date, end: args.end_date },
        logs: filteredLogs.map((l) => ({
          date: l.logDate, weather: l.weatherConditions, headcount: l.totalHeadcount,
          work: l.workPerformed, delays: l.delays, delay_hours: l.delayHours,
        })),
      }, null, 2);

      return {
        messages: [
          {
            role: 'user' as const,
            content: {
              type: 'text' as const,
              text: `Summarize these construction daily logs into a concise executive narrative suitable for owner/stakeholder distribution:\n\n${context}\n\nInclude:\n1. Overall progress narrative\n2. Workforce summary\n3. Weather impacts\n4. Key accomplishments\n5. Delays or issues\n6. Look-ahead items`,
            },
          },
        ],
      };
    },
  );

  // ── Change Order Analysis ────────────────────────────────────────────

  server.prompt(
    'change-order-analysis',
    'Analyzes change order reasonableness, compares to historical, drafts negotiation points',
    { change_order_id: z.string().uuid() },
    async (args) => {
      const db = getDb();
      const [co] = await db.select().from(changeOrders).where(eq(changeOrders.id, args.change_order_id)).limit(1);
      if (!co) {
        return { messages: [{ role: 'user' as const, content: { type: 'text' as const, text: 'Change order not found.' } }] };
      }

      const [project] = await db.select().from(projects).where(eq(projects.id, co.projectId)).limit(1);
      const allCos = await db.select().from(changeOrders).where(eq(changeOrders.projectId, co.projectId));
      const budget = await db.select().from(budgetLines).where(eq(budgetLines.projectId, co.projectId));

      const totalBudget = budget.reduce((s, b) => s + Number(b.originalBudget || 0) + Number(b.approvedChanges || 0), 0);

      const context = JSON.stringify({
        project: project ? { name: project.name, contract_amount: project.contractAmount } : null,
        change_order: { number: co.coNumber, title: co.title, description: co.description, reason: co.reason, cost_amount: co.costAmount, schedule_days: co.scheduleDays, markup: co.markupAmount, total: co.totalWithMarkup },
        historical: { total_cos: allCos.length, total_approved_amount: allCos.filter((c) => c.status === 'approved').reduce((s, c) => s + Number(c.totalWithMarkup || 0), 0), total_budget: totalBudget },
      }, null, 2);

      return {
        messages: [
          {
            role: 'user' as const,
            content: {
              type: 'text' as const,
              text: `Analyze this construction change order for reasonableness and provide negotiation guidance:\n\n${context}\n\nProvide:\n1. Cost reasonableness assessment\n2. Comparison to project history and industry norms\n3. Markup analysis\n4. Schedule impact assessment\n5. Negotiation points and recommendations\n6. Risk considerations`,
            },
          },
        ],
      };
    },
  );
}
