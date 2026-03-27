import { defineConfig } from "astro/config";

const repoSlug = process.env.GITHUB_REPOSITORY?.split("/")[1] ?? "linkar";
const owner = process.env.GITHUB_REPOSITORY?.split("/")[0] ?? "jovesus";
const site = process.env.SITE_URL ?? `https://${owner}.github.io`;
const base = process.env.GITHUB_ACTIONS ? `/${repoSlug}/` : "/";

export default defineConfig({
  site,
  base,
});
