import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";

const tutorials = defineCollection({
  loader: glob({ pattern: "**/*.{md,mdx}", base: "./src/content/tutorials" }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    order: z.number(),
    status: z.enum(["draft", "ready"]).default("draft"),
  }),
});

const explanations = defineCollection({
  loader: glob({ pattern: "**/*.{md,mdx}", base: "./src/content/explanations" }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    order: z.number(),
  }),
});

export const collections = {
  tutorials,
  explanations,
};
