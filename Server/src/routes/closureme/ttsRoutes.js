const express = require("express");
const ttsController = require("../../controllers/closureme/ttsController");
const authMiddleware = require("../../middlewares/authMiddleware");
const router = express.Router();

router.post("/tts-prepare", authMiddleware, ttsController.prepareTTS);

module.exports = router;