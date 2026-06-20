import { z } from 'zod';
import { eq, and, ilike, or } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { rfis, changeOrders, dailyLogs, estimates } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'search_project_docs',
    'Full-text search across project documents and records',
    {
      project_id: z.string().uuid(),
      query: z.string().min(1),
      doc_type: z.enum(['rfi', 'co', 'daily_log', 'estimate', 'submittal', 'all']).optional().default('all'),
    },
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'search_project_docs', async () => {
      await validateProjectAccess(args.project_id, ctx.orgId);
      const db = getDb();
      const q = `%${args.query}%`;
      const results: any[] = [];

      if (args.doc_type === 'all' || args.doc_type === 'rfi') {
        const rfiResults = await db.select().from(rfis).where(
          and(eq(rfis.projectId, args.project_id), or(ilike(rfis.subject, q), ilike(rfis.question, q), ilike(rfis.answer, q))),
        );
        results.push(...rfiResults.map((r) => ({
          type: 'rfi', id: r.id, title: r.subject,
          snippet: (r.question || '').substring(0, 200),
          date: r.createdAt, status: r.status, number: r.rfiNumber,
        })));
      }

      if (args.doc_type === 'all' || args.doc_type === 'co') {
        const coResults = await db.select().from(changeOrders).where(
          and(eq(changeOrders.projectId, args.project_id), or(ilike(changeOrders.title, q), ilike(changeOrders.description, q))),
        );
        results.push(...coResults.map((c) => ({
          type: 'change_order', id: c.id, title: c.title,
          snippet: (c.description || '').substring(0, 200),
          date: c.createdAt, status: c.status, number: c.coNumber,
        })));
      }

      if (args.doc_type === 'all' || args.doc_type === 'daily_log') {
        const logResults = await db.select().from(dailyLogs).where(
          and(eq(dailyLogs.projectId, args.project_id), or(ilike(dailyLogs.workPerformed, q), ilike(dailyLogs.notes, q))),
        );
        results.push(...logResults.map((l) => ({
          type: 'daily_log', id: l.id, title: `Daily Log - ${l.logDate}`,
          snippet: (l.workPerformed || '').substring(0, 200),
          date: l.logDate,
        })));
      }

      if (args.doc_type === 'all' || args.doc_type === 'estimate') {
        const estResults = await db.select().from(estimates).where(
          and(eq(estimates.projectId, args.project_id), or(ilike(estimates.name, q), ilike(estimates.notes, q))),
        );
        results.push(...estResults.map((e) => ({
          type: 'estimate', id: e.id, title: e.name,
          snippet: (e.notes || '').substring(0, 200),
          date: e.createdAt, status: e.status,
        })));
      }

      return textContent({ results, total: results.length, query: args.query });
      });
    },
  );
}
