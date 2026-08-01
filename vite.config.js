import vinext from "vinext";

const bundleSitesServerDependencies = {
  name: "soillens:bundle-sites-server-dependencies",
  enforce: "post",
  configEnvironment(name, config) {
    if (name !== "ssr" || !Array.isArray(config.resolve?.external)) return;
    config.resolve.external = config.resolve.external.filter(
      (id) =>
        id !== "react" &&
        id !== "react-dom" &&
        id !== "react-dom/server" &&
        id !== "react-dom/server.edge" &&
        id !== "react/jsx-runtime",
    );
  },
};

export default {
  plugins: [
    vinext({
      // The root-level app/ directory is the Python backend, not a Next.js
      // App Router directory. The public site intentionally uses pages/.
      disableAppRouter: true,
    }),
    bundleSitesServerDependencies,
  ],
};
