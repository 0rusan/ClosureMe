// routes/api/builderRoutes.js
const express = require("express");
const builderController = require("../../controllers/closureme/builderController");
const authMiddleware = require("../../middlewares/authMiddleware");
const router = express.Router();

router.post("/build-agent", authMiddleware, builderController.buildAgentBundle);

module.exports = router;
