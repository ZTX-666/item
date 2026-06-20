import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { ResourceTemplate } from '@modelcontextprotocol/sdk/server/mcp.js';
import { getProjectSummary } from './project-summary.js';
import { getBudgetSnapshot } from './budget-snapshot.js';
import { getScheduleSnapshot } from './schedule-snapshot.js';
import { getRfiSnapshot } from './rfi-snapshot.js';

export function registerResources(server: McpServer) {
  server.resource(
    'project-summary',
    new ResourceTemplate('project://{id}/summary', { list: undefined }),
    async (uri, params) => {
      const id = params.id as string;
      const data = await getProjectSummary(id);
      return {
        contents: [
          {
            uri: uri.href,
            mimeType: 'application/json',
            text: JSON.stringify(data, null, 2),
          },
        ],
      };
    },
  );

  server.resource(
    'project-budget',
    new ResourceTemplate('project://{id}/budget', { list: undefined }),
    async (uri, params) => {
      const id = params.id as string;
      const data = await getBudgetSnapshot(id);
      return {
        contents: [
          {
            uri: uri.href,
            mimeType: 'application/json',
            text: JSON.stringify(data, null, 2),
          },
        ],
      };
    },
  );

  server.resource(
    'project-schedule',
    new ResourceTemplate('project://{id}/schedule', { list: undefined }),
    async (uri, params) => {
      const id = params.id as string;
      const data = await getScheduleSnapshot(id);
      return {
        contents: [
          {
            uri: uri.href,
            mimeType: 'application/json',
            text: JSON.stringify(data, null, 2),
          },
        ],
      };
    },
  );

  server.resource(
    'project-rfis',
    new ResourceTemplate('project://{id}/rfis', { list: undefined }),
    async (uri, params) => {
      const id = params.id as string;
      const data = await getRfiSnapshot(id);
      return {
        contents: [
          {
            uri: uri.href,
            mimeType: 'application/json',
            text: JSON.stringify(data, null, 2),
          },
        ],
      };
    },
  );
}
