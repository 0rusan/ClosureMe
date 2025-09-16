const express = require('express');
const router = express.Router();

const { register } = require('../controllers/auth/registerController.js');
const { login } = require('../controllers/auth/loginController.js');
const authMiddleware = require('../middlewares/authMiddleware.js');

router.post('/register', register);
router.post('/login', login);

router.get('/auth/me', authMiddleware, (req, res) => {
  res.json({
    ok: true,
    user_id: req.user_id,
    username: req.username || "用戶"
  });
});

module.exports = router;
