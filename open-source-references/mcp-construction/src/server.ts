import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';

// Tool registrations
import { register as createProject } from './tools/projects/create-project.js';
import { register as getProject } from './tools/projects/get-project.js';
import { register as listProjects } from './tools/projects/list-projects.js';
import { register as updateProject } from './tools/projects/update-project.js';
import { register as getProjectDashboard } from './tools/projects/get-project-dashboard.js';

import { register as createEstimate } from './tools/estimates/create-estimate.js';
import { register as getEstimate } from './tools/estimates/get-estimate.js';
import { register as updateLineItem } from './tools/estimates/update-line-item.js';
import { register as compareEstimates } from './tools/estimates/compare-estimates.js';
import { register as generateEstimateReport } from './tools/estimates/generate-estimate-report.js';
import { register as importCostData } from './tools/estimates/import-cost-data.js';

import { register as createRfi } from './tools/rfis/create-rfi.js';
import { register as listRfis } from './tools/rfis/list-rfis.js';
import { register as getRfi } from './tools/rfis/get-rfi.js';
import { register as respondToRfi } from './tools/rfis/respond-to-rfi.js';
import { register as draftRfiResponse } from './tools/rfis/draft-rfi-response.js';

import { register as createChangeOrder } from './tools/change-orders/create-change-order.js';
import { register as evaluateChangeOrderImpact } from './tools/change-orders/evaluate-change-order-impact.js';
import { register as approveChangeOrder } from './tools/change-orders/approve-change-order.js';
import { register as getChangeOrderLog } from './tools/change-orders/get-change-order-log.js';

import { register as createDailyLog } from './tools/daily-logs/create-daily-log.js';
import { register as getDailyLog } from './tools/daily-logs/get-daily-log.js';
import { register as summarizeDailyLogs } from './tools/daily-logs/summarize-daily-logs.js';
import { register as generateWeeklyReport } from './tools/daily-logs/generate-weekly-report.js';

import { register as getBudgetByCostCode } from './tools/budget/get-budget-by-cost-code.js';
import { register as flagBudgetOverruns } from './tools/budget/flag-budget-overruns.js';
import { register as forecastCompletionCost } from './tools/budget/forecast-completion-cost.js';
import { register as trackCommittedCosts } from './tools/budget/track-committed-costs.js';

import { register as getSchedule } from './tools/schedule/get-schedule.js';
import { register as checkCriticalPath } from './tools/schedule/check-critical-path.js';
import { register as flagDelayedTasks } from './tools/schedule/flag-delayed-tasks.js';
import { register as calculateFloat } from './tools/schedule/calculate-float.js';

import { register as listSubcontractors } from './tools/subcontractors/list-subcontractors.js';
import { register as getSubPerformance } from './tools/subcontractors/get-sub-performance.js';
import { register as compareBids } from './tools/subcontractors/compare-bids.js';
import { register as generateSubScorecard } from './tools/subcontractors/generate-sub-scorecard.js';

import { register as searchProjectDocs } from './tools/documents/search-project-docs.js';
import { register as getSubmittalStatus } from './tools/documents/get-submittal-status.js';
import { register as generateAiaPaymentApp } from './tools/documents/generate-aia-payment-app.js';
import { register as createLienWaiver } from './tools/documents/create-lien-waiver.js';

import { register as logSafetyIncident } from './tools/safety/log-safety-incident.js';
import { register as getOshaStatus } from './tools/safety/get-osha-status.js';
import { register as generateToolboxTalk } from './tools/safety/generate-toolbox-talk.js';
import { register as trackCertifications } from './tools/safety/track-certifications.js';

import { register as createUser } from './tools/users/create-user.js';
import { register as listUsers } from './tools/users/list-users.js';
import { register as updateUserRole } from './tools/users/update-user-role.js';
import { register as removeUser } from './tools/users/remove-user.js';
import { register as getOrgSettings } from './tools/users/get-org-settings.js';
import { register as updateOrgSettings } from './tools/users/update-org-settings.js';

// Resources
import { registerResources } from './resources/index.js';

// Prompts
import { registerPrompts } from './prompts/index.js';

export function createMcpServer(): McpServer {
  const server = new McpServer({
    name: '@constructionai/mcp-server',
    version: '1.0.0',
  });

  // Register all 44 tools
  createProject(server);
  getProject(server);
  listProjects(server);
  updateProject(server);
  getProjectDashboard(server);

  createEstimate(server);
  getEstimate(server);
  updateLineItem(server);
  compareEstimates(server);
  generateEstimateReport(server);
  importCostData(server);

  createRfi(server);
  listRfis(server);
  getRfi(server);
  respondToRfi(server);
  draftRfiResponse(server);

  createChangeOrder(server);
  evaluateChangeOrderImpact(server);
  approveChangeOrder(server);
  getChangeOrderLog(server);

  createDailyLog(server);
  getDailyLog(server);
  summarizeDailyLogs(server);
  generateWeeklyReport(server);

  getBudgetByCostCode(server);
  flagBudgetOverruns(server);
  forecastCompletionCost(server);
  trackCommittedCosts(server);

  getSchedule(server);
  checkCriticalPath(server);
  flagDelayedTasks(server);
  calculateFloat(server);

  listSubcontractors(server);
  getSubPerformance(server);
  compareBids(server);
  generateSubScorecard(server);

  searchProjectDocs(server);
  getSubmittalStatus(server);
  generateAiaPaymentApp(server);
  createLienWaiver(server);

  logSafetyIncident(server);
  getOshaStatus(server);
  generateToolboxTalk(server);
  trackCertifications(server);

  // User & Org management tools
  createUser(server);
  listUsers(server);
  updateUserRole(server);
  removeUser(server);
  getOrgSettings(server);
  updateOrgSettings(server);

  // Register resources and prompts
  registerResources(server);
  registerPrompts(server);

  return server;
}
