import adapter from "@sveltejs/adapter-static";

/** @type {import('@sveltejs/kit').Config} */
const config = {
  kit: {
    adapter: adapter({
      // Serve the SPA shell for all unmatched paths so client-side
      // routing works without server-side rendering.
      fallback: "index.html",
    }),
    // Base path must match the Python StaticFiles mount point.
    paths: {
      base: "/app",
    },
    // Avoid collisions with the Python /static mount.
    appDir: "_app",
  },
};

export default config;
