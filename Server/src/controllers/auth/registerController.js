// registerController.js 
const bcrypt = require('bcryptjs');
const pool = require('../../models/db');
const { isValidEmail } = require('../../../public/utils/validate');

exports.register = async (req, res) => {
    try {
        const { username, email, password } = req.body;

        if (!username || !email || !password) {
            return res.status(400).json({ message: '請填寫所有欄位' });
        }
        if (!isValidEmail(email)) {
            return res.status(400).json({ message: '請輸入正確的電子郵件格式' });
        }

        const hashedPassword = await bcrypt.hash(password, 10);

        const result = await pool.query(
            'INSERT INTO users (username, email, password) VALUES ($1, $2, $3) RETURNING id, username, email',
            [username, email, hashedPassword]
        );

        const newUser = result.rows[0];

        return res.status(201).json({
            message: "註冊成功",
            user: {
                id: newUser.id,
                username: newUser.username,
                email: newUser.email
            }
        });

    } catch (error) {
        console.error("❌ 註冊錯誤：", error);

        if (error.code === '23505') {
            return res.status(400).json({ message: "帳號或信箱已被註冊" });
        }

        return res.status(500).json({ message: "伺服器錯誤" });
    }
};