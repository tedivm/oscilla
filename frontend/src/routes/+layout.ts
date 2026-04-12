// Disable SSR and prerendering — this app runs entirely client-side as a SPA.
// adapter-static requires either prerender=true or fallback configured; we use
// fallback: 'index.html' in svelte.config.js to serve the shell for all paths.
export const ssr = false;
export const prerender = false;
