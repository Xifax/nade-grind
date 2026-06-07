// @ts-check
import { defineConfig } from 'astro/config';

// https://astro.build/config
export default defineConfig({
  site: "https://xifax.gitlab.io",
  base: process.env.PUBLIC_BASE || "/",
});
