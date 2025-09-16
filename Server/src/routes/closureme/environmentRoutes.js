const express = require("express");
const router = express.Router();
const authMiddleware = require("../../middlewares/authMiddleware");
const environmentController = require("../../controllers/closureme/environmentController");

router.post("/write-environment", authMiddleware, environmentController.writeEnvironment);

module.exports = router;