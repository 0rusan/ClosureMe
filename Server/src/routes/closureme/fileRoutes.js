// 檔案管理系統 API
const express = require("express");
const router = express.Router();
const fileController = require("../../controllers/closureme/fileController");
const authMiddleware = require("../../middlewares/authMiddleware");

router.get("/files", authMiddleware, fileController.getFiles);
router.delete("/delete-character", authMiddleware, fileController.deleteCharacter);
router.post("/rename-character", authMiddleware, fileController.renameCharacter);
router.get("/characters", authMiddleware, fileController.getMainList);
router.get("/main-images-for-binding", authMiddleware, fileController.getMainImagesForBinding);

module.exports = router;