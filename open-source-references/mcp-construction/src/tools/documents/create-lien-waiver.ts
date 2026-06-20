import { z } from 'zod';
import { eq } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { projects } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

const WAIVER_TEMPLATES: Record<string, { title: string; text: string }> = {
  conditional_progress: {
    title: 'CONDITIONAL WAIVER AND RELEASE ON PROGRESS PAYMENT',
    text: 'Upon receipt of a check from {owner} in the sum of ${amount} payable to {claimant} and when the check has been properly endorsed and has been paid by the bank on which it is drawn, this document becomes effective to release any mechanic\'s lien, stop payment notice, or bond right the claimant has on the job of {owner} located at {address} to the following extent.',
  },
  unconditional_progress: {
    title: 'UNCONDITIONAL WAIVER AND RELEASE ON PROGRESS PAYMENT',
    text: 'The claimant, {claimant}, has been paid and has received a progress payment in the sum of ${amount} for labor, services, equipment, or material furnished to {owner} on the job of {owner} located at {address}, and does hereby release any mechanic\'s lien, stop payment notice, or bond right that the claimant has on the above referenced job to the following extent.',
  },
  conditional_final: {
    title: 'CONDITIONAL WAIVER AND RELEASE ON FINAL PAYMENT',
    text: 'Upon receipt of a check from {owner} in the sum of ${amount} payable to {claimant} and when the check has been properly endorsed and has been paid by the bank on which it is drawn, this document becomes effective as a final waiver and release of any mechanic\'s lien, stop payment notice, or bond right the claimant has on the job of {owner} located at {address}.',
  },
  unconditional_final: {
    title: 'UNCONDITIONAL WAIVER AND RELEASE ON FINAL PAYMENT',
    text: 'The claimant, {claimant}, has been paid in full for all labor, services, equipment, or material furnished to {owner} on the job of {owner} located at {address}, and does hereby waive and release any right to a mechanic\'s lien, stop payment notice, and any right to make a claim on a payment bond for said work.',
  },
};

export function register(server: McpServer) {
  server.tool(
    'create_lien_waiver',
    'Generate conditional/unconditional lien waiver data',
    {
      project_id: z.string().uuid(),
      waiver_type: z.enum(['conditional_progress', 'unconditional_progress', 'conditional_final', 'unconditional_final']),
      claimant_name: z.string(),
      through_date: z.string().describe('Date YYYY-MM-DD'),
      amount: z.number().min(0),
    },
    async (args, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'create_lien_waiver', async () => {
      await validateProjectAccess(args.project_id, ctx.orgId);
      const db = getDb();
      const [project] = await db.select().from(projects).where(eq(projects.id, args.project_id)).limit(1);
      if (!project) return textContent({ error: 'Project not found' });

      const template = WAIVER_TEMPLATES[args.waiver_type];
      const address = [project.address, project.city, project.state, project.zip].filter(Boolean).join(', ');
      const ownerName = project.ownerName || 'Property Owner';

      const waiverText = template.text
        .replace(/{owner}/g, ownerName)
        .replace(/{claimant}/g, args.claimant_name)
        .replace(/{amount}/g, args.amount.toLocaleString('en-US', { minimumFractionDigits: 2 }))
        .replace(/{address}/g, address || 'Project Site');

      return textContent({
        waiver: {
          title: template.title,
          waiver_type: args.waiver_type,
          project_name: project.name,
          project_number: project.projectNumber,
          project_address: address,
          owner: ownerName,
          claimant: args.claimant_name,
          through_date: args.through_date,
          amount: args.amount,
          text: waiverText,
          signature_required: true,
          date_field: new Date().toISOString().split('T')[0],
        },
      });
      });
    },
  );
}
