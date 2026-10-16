// Static config lives in app.json. EXPO_WEB_BASE_URL (e.g. "/demo") is only for hosting the web build in a sub-folder.
module.exports = ({ config }) => ({
  ...config,
  experiments: { ...config.experiments, ...(process.env.EXPO_WEB_BASE_URL ? { baseUrl: process.env.EXPO_WEB_BASE_URL } : {}) },
});
