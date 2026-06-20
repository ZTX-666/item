import pg from 'pg';
import bcrypt from 'bcrypt';

async function seed() {
  const databaseUrl = process.env.DATABASE_URL || 'postgresql://constructionai:constructionai@localhost:5432/construction_mcp';
  const client = new pg.Client({ connectionString: databaseUrl });
  await client.connect();

  console.log('Seeding database...');

  // Create demo organization
  const orgResult = await client.query(`
    INSERT INTO organizations (name, slug, plan, subscription_status, trial_ends_at)
    VALUES ('Demo Construction Co', 'demo-construction', 'trial', 'trialing', NOW() + INTERVAL '14 days')
    ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
    RETURNING id
  `);
  const orgId = orgResult.rows[0].id;
  console.log(`Organization: ${orgId}`);

  // Create demo user
  const passwordHash = await bcrypt.hash('demo123', 10);
  const userResult = await client.query(`
    INSERT INTO users (org_id, email, name, password_hash, role)
    VALUES ($1, 'demo@constructionai.com', 'Demo User', $2, 'owner')
    ON CONFLICT (org_id, email) DO UPDATE SET name = EXCLUDED.name
    RETURNING id
  `, [orgId, passwordHash]);
  const userId = userResult.rows[0].id;
  console.log(`User: ${userId}`);

  // Create demo project
  const projectResult = await client.query(`
    INSERT INTO projects (org_id, name, project_number, address, city, state, zip, project_type, contract_type, contract_amount, start_date, estimated_completion, status, owner_name, architect_name, superintendent, project_manager)
    VALUES ($1, 'Riverside Office Complex', 'P-2024-001', '1234 River Road', 'Austin', 'TX', '78701', 'commercial', 'gmp', 15000000, '2024-03-01', '2025-06-30', 'active', 'Riverside Development LLC', 'Smith & Associates Architects', 'John Martinez', 'Sarah Chen')
    ON CONFLICT DO NOTHING
    RETURNING id
  `, [orgId]);

  if (projectResult.rows.length > 0) {
    const projectId = projectResult.rows[0].id;
    console.log(`Project: ${projectId}`);

    // Budget lines
    const budgetData = [
      ['03', 'Concrete', 1200000, 50000, 180000, 850000, 72],
      ['04', 'Masonry', 450000, 0, 120000, 380000, 60],
      ['05', 'Metals/Structural Steel', 2100000, 150000, 1800000, 1650000, 78],
      ['06', 'Wood & Plastics', 350000, 0, 45000, 280000, 55],
      ['07', 'Thermal & Moisture Protection', 680000, 25000, 200000, 520000, 65],
      ['08', 'Doors & Windows', 920000, 0, 150000, 750000, 45],
      ['09', 'Finishes', 1800000, 0, 50000, 100000, 10],
      ['15', 'Mechanical', 2500000, 100000, 800000, 1200000, 40],
      ['16', 'Electrical', 1900000, 75000, 600000, 950000, 42],
      ['31', 'Earthwork', 400000, 0, 380000, 400000, 100],
    ];

    for (const [code, desc, budget, changes, committed, actual, pct] of budgetData) {
      await client.query(`
        INSERT INTO budget_lines (project_id, cost_code, description, original_budget, approved_changes, committed_costs, actual_costs, percent_complete)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (project_id, cost_code) DO NOTHING
      `, [projectId, code, desc, budget, changes, committed, actual, pct]);
    }

    // Schedule tasks
    const tasks = [
      ['Site Preparation', '01', '2024-03-01', '2024-04-15', 100, true, 0],
      ['Foundation', '02', '2024-04-01', '2024-06-15', 100, true, 0],
      ['Structural Steel', '03', '2024-06-01', '2024-09-30', 78, true, 0],
      ['Exterior Envelope', '04', '2024-08-15', '2024-12-31', 55, true, 2],
      ['MEP Rough-In', '05', '2024-09-01', '2025-02-28', 40, true, 0],
      ['Interior Framing', '06', '2024-11-01', '2025-02-15', 30, false, 8],
      ['Finishes', '07', '2025-01-15', '2025-05-15', 10, false, 15],
      ['Commissioning', '08', '2025-05-01', '2025-06-15', 0, true, 20],
      ['Punch List', '09', '2025-06-01', '2025-06-30', 0, false, 30],
    ];

    for (const [name, wbs, start, end, pct, critical, float] of tasks) {
      const status = pct === 100 ? 'complete' : Number(pct) > 0 ? 'in_progress' : 'not_started';
      await client.query(`
        INSERT INTO schedule_tasks (project_id, task_name, wbs_code, start_date, end_date, percent_complete, is_critical_path, total_float_days, free_float_days, status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        ON CONFLICT DO NOTHING
      `, [projectId, name, wbs, start, end, pct, critical, float, float, status]);
    }

    // Sample RFIs
    await client.query(`
      INSERT INTO rfis (project_id, rfi_number, subject, question, status, priority, assigned_to, created_by)
      VALUES
        ($1, 1, 'Foundation reinforcement detail', 'Please clarify the rebar spacing at grid intersection B-4. Drawings show #5 @ 12" OC but structural notes reference #6 @ 10" OC.', 'answered', 'high', 'Smith & Associates', $2),
        ($1, 2, 'Waterproofing membrane at elevator pit', 'Spec section 07 11 00 references crystalline waterproofing but detail 4/S-201 shows sheet membrane. Please confirm intended system.', 'open', 'normal', 'Smith & Associates', $2),
        ($1, 3, 'Steel connection at grid C-7', 'RFI regarding moment connection detail that appears to conflict with architectural clearance requirements.', 'open', 'urgent', 'Smith & Associates', $2)
      ON CONFLICT (project_id, rfi_number) DO NOTHING
    `, [projectId, userId]);

    // Sample Change Order
    await client.query(`
      INSERT INTO change_orders (project_id, co_number, title, description, reason, status, cost_amount, schedule_days, markup_amount, total_with_markup, created_by)
      VALUES ($1, 1, 'Additional soil remediation', 'Unforeseen contaminated soil discovered during excavation requiring additional remediation per environmental report.', 'unforeseen_condition', 'approved', 185000, 12, 27750, 212750, $2)
      ON CONFLICT (project_id, co_number) DO NOTHING
    `, [projectId, userId]);

    console.log('Demo data seeded successfully');
  }

  await client.end();
}

seed().catch((err) => {
  console.error('Seed failed:', err);
  process.exit(1);
});
