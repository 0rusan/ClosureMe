const express = require("express");
const analysisController = require("../../controllers/closureme/analysisController");
const authMiddleware = require("../../middlewares/authMiddleware");
const router = express.Router();

router.post("/analysis-txt", authMiddleware, analysisController.runAnalysisTxt);

module.exports = router;