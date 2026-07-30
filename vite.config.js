import vinext from "vinext";

export default {
  plugins: [
    vinext({
      // The root-level app/ directory is the Python backend, not a Next.js
      // App Router directory. The public site intentionally uses pages/.
      disableAppRouter: true,
    }),
  ],
};
