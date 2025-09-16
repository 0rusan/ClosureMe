//集中掛載路由
const authRoutes = require('./src/routes/authRoutes');
const characterRoutes = require("./src/routes/closureme/characterRoutes");
const fileRoutes = require("./src/routes/closureme/fileRoutes");
const ttsRoutes = require("./src/routes/closureme/ttsRoutes");
const environmentRoutes = require("./src/routes/closureme/environmentRoutes");
const analysisRoutes = require("./src/routes/closureme/analysisRoutes");
const builderRoutes = require("./src/routes/closureme/builderRoutes");

module.exports = (app) => {
    app.use('/api', authRoutes);
    app.use("/api", characterRoutes);
    app.use("/api", fileRoutes);
    app.use("/api", ttsRoutes);
    app.use("/api", environmentRoutes);
    app.use("/api", analysisRoutes);
    app.use("/api", builderRoutes);
};