import { z } from 'zod';
import { eq, and, desc } from 'drizzle-orm';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getDb } from '../../db/index.js';
import { rfis, projects } from '../../db/schema.js';
import { requireContext, executeWithMiddleware, validateProjectAccess, textContent, errorContent } from '../../lib/tool-helpers.js';

export function register(server: McpServer) {
  server.tool(
    'draft_rfi_response',
    'AI-assisted: Generates draft RFI response using project context and similar past RFIs. Returns structured draft for human review.',
    {
      rfi_id: z.string().uuid(),
      context: z.string().optional(),
      reference_spec_sections: z.array(z.string()).optional(),
      tone: z.enum(['formal', 'concise', 'detailed']).optional(),
    },
    async (params, extra) => {
      const ctx = requireContext((extra as any).sessionId);
      return executeWithMiddleware(ctx, 'draft_rfi_response', async () => {
        try {
          const db = getDb();
          const tone = params.tone ?? 'formal';

          // Fetch the target RFI
          const [rfi] = await db
            .select()
            .from(rfis)
            .where(eq(rfis.id, params.rfi_id));

          if (!rfi) {
            return errorContent(`RFI not found: ${params.rfi_id}`);
          }

          await validateProjectAccess(rfi.projectId, ctx.orgId);

          // Fetch project details
          const [project] = await db
            .select()
            .from(projects)
            .where(eq(projects.id, rfi.projectId));

          if (!project) {
            return errorContent(`Project not found for RFI: ${rfi.projectId}`);
          }

          // Query similar past RFIs (same project, answered status)
          const pastRfis = await db
            .select()
            .from(rfis)
            .where(
              and(
                eq(rfis.projectId, rfi.projectId),
                eq(rfis.status, 'answered'),
              ),
            )
            .orderBy(desc(rfis.respondedAt))
            .limit(5);

          // Build spec reference string
          const specRefs = params.reference_spec_sections?.length
            ? `Reference specification sections: ${params.reference_spec_sections.join(', ')}. `
            : '';

          // Build additional context string
          const additionalContext = params.context
            ? `Additional context: ${params.context}. `
            : '';

          // Generate a template draft response based on tone
          let draftBody: string;
          switch (tone) {
            case 'concise':
              draftBody =
                `In response to RFI #${rfi.rfiNumber} ("${rfi.subject}"): ` +
                `${specRefs}${additionalContext}` +
                `The question posed is: "${rfi.question}" ` +
                `[Insert concise answer here]. ` +
                `Please confirm receipt and proceed accordingly.`;
              break;
            case 'detailed':
              draftBody =
                `RE: RFI #${rfi.rfiNumber} - ${rfi.subject}\n\n` +
                `Project: ${project.name} (${project.projectNumber ?? 'N/A'})\n\n` +
                `Question:\n${rfi.question}\n\n` +
                `${specRefs}${additionalContext}\n` +
                `Response:\n` +
                `After thorough review of the project documents and applicable specifications, ` +
                `the following response is provided for your consideration:\n\n` +
                `[Insert detailed response here]\n\n` +
                `Impact Assessment:\n` +
                `- Cost Impact: ${rfi.costImpact ? 'Yes - to be determined' : 'None anticipated'}\n` +
                `- Schedule Impact: ${rfi.scheduleImpact ? 'Yes - to be determined' : 'None anticipated'}\n\n` +
                `Please review and advise if further clarification is required.`;
              break;
            default: // formal
              draftBody =
                `RE: RFI #${rfi.rfiNumber} - ${rfi.subject}\n\n` +
                `Project: ${project.name}\n\n` +
                `In response to your inquiry regarding "${rfi.question}", ` +
                `${specRefs}${additionalContext}` +
                `please find our response below:\n\n` +
                `[Insert formal response here]\n\n` +
                `Should you require additional information or clarification, ` +
                `please do not hesitate to contact us.`;
              break;
          }

          // Build the referenced past RFIs summary
          const referencedPastRfis = pastRfis.map((pastRfi) => ({
            rfi_id: pastRfi.id,
            rfi_number: pastRfi.rfiNumber,
            subject: pastRfi.subject,
            question: pastRfi.question,
            answer: pastRfi.answer,
            responded_at: pastRfi.respondedAt,
          }));

          return textContent({
            rfi: {
              id: rfi.id,
              rfi_number: rfi.rfiNumber,
              subject: rfi.subject,
              question: rfi.question,
              priority: rfi.priority,
              due_date: rfi.dueDate,
              cost_impact: rfi.costImpact,
              schedule_impact: rfi.scheduleImpact,
            },
            project: {
              id: project.id,
              name: project.name,
              project_number: project.projectNumber,
            },
            draft_response: draftBody,
            referenced_past_rfis: referencedPastRfis,
            confidence_score: 0.7,
            suggested_attachments: [],
            tone,
            note: 'This is an AI-generated draft. Please review and edit before submitting as the official response.',
          });
        } catch (err) {
          return errorContent(err instanceof Error ? err.message : 'Failed to draft RFI response');
        }
      });
    },
  );
}
