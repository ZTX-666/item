import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import pg from 'pg';

const __dirname = dirname(fileURLToPath(import.meta.url));

async function migrate() {
  const databaseUrl = process.env.DATABASE_URL;
  if (!databaseUrl) {
    console.error('DATABASE_URL environment variable is required');
    process.exit(1);
  }

  const client = new pg.Client({ connectionString: databaseUrl });
  await client.connect();

  console.log('Running migrations...');

  try {
    const migrationPath = join(__dirname, '../../drizzle/0001_initial.sql');
    const sql = readFileSync(migrationPath, 'utf-8');
    await client.query(sql);
    console.log('Migration 0001_initial.sql applied successfully');
  } catch (err: any) {
    if (err.code === '42P07') {
      console.log('Tables already exist, skipping...');
    } else {
      throw err;
    }
  }

  await client.end();
  console.log('Migrations complete');
}

migrate().catch((err) => {
  console.error('Migration failed:', err);
  process.exit(1);
});
