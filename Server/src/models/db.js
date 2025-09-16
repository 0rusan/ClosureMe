// PostgreSQL 連線設定
const { Pool } = require("pg");
require("dotenv").config();

const url = process.env.DATABASE_URL || "";
let ssl = false;
try {
  const host = new URL(url).hostname || "";
  if (host.endsWith("render.com")) ssl = { rejectUnauthorized: false };
} catch (_) {} 

if (!ssl && String(process.env.DB_SSL).toLowerCase() === "true") {
  ssl = { rejectUnauthorized: false };
}

const pool = new Pool({
  connectionString: url,
  ssl,
});

module.exports = pool;