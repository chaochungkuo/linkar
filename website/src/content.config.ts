import { defineCollection, z } from "astro:content";

const tutorials = defineCollection({
  schema: z.object({
    title: z.string(),
    description: z.string(),
    order: z.number(),
    status: z.enum(["draft", "ready"]).default("draft"),
  }),
});

const explanations = defineCollection({
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
