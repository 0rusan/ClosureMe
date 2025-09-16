// server.js
const express = require('express');
const path = require('path');
const setupRoutes = require('./setupRoutes');
const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.urlencoded({ extended: true }));

app.use(express.static(path.join(__dirname, 'public')));

app.get('/healthz', (_req, res) => res.send('ok'));

const pool = require('./src/models/db');
app.get('/debug/db', async (_req, res) => {
  try {
    const { rows } = await pool.query('SELECT NOW() as now');
    res.json({ ok: true, now: rows[0].now });
  } catch (err) {
    console.error('DB connection error:', err);
    res.status(500).json({ ok: false, error: err.message });
  }
});

app.get("/", (req, res) => {
  res.sendFile(path.join(__dirname, "frontPage.html"));
});

setupRoutes(app);

app.listen(PORT, '0.0.0.0', () => { console.log(`Server is running at http://localhost:${PORT}`); });