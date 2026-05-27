import { getCollection } from "astro:content";
import { docsNav, withBase } from "../lib/docsNav";

type SearchItem = {
  title: string;
  description: string;
  href: string;
  section: string;
  content: string;
};

const base = import.meta.env.BASE_URL;

function normalizeMarkdown(value: string): string {
  return value
    .replace(/```[a-zA-Z0-9_-]*\n?/g, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/[`*_#[\](){}>|-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export async function GET() {
  const tutorials = await getCollection("tutorials");
  const explanations = await getCollection("explanations");

  const navByHref = new Map<string, { section: string; description?: string }>();
  for (const group of docsNav) {
    for (const item of group.items) {
      navByHref.set(item.href, { section: group.title, description: item.description });
    }
  }

  const entries: SearchItem[] = [
    {
      title: "Linkar documentation",
      description: "Overview, installation, public interfaces, and the project model.",
      href: base,
      section: "Start",
      content: "Linkar documentation installation CLI local API MCP packs projects templates runs collect clean inspect",
    },
    {
      title: "Technical documentation",
      description: "Map of Linkar guides, concepts, automation pages, and references.",
      href: withBase(base, "docs/"),
      section: "Start",
      content: docsNav.flatMap((group) => [group.title, group.description, ...group.items.map((item) => `${item.title} ${item.description}`)]).join(" "),
    },
    {
      title: "Examples",
      description: "Bundled packs for learning template authoring, chaining, binding overrides, pack selection, and remote packs.",
      href: withBase(base, "examples/"),
      section: "Reference",
      content: "basic chaining binding_overrides pack_management remote examples packs templates bindings remote GitHub",
    },
  ];

  for (const entry of explanations) {
    const href = `explanations/${entry.slug}/`;
    const nav = navByHref.get(href);
    entries.push({
      title: entry.data.title,
      description: nav?.description ?? entry.data.description,
      href: withBase(base, href),
      section: nav?.section ?? "Concepts",
      content: normalizeMarkdown(entry.body),
    });
  }

  for (const entry of tutorials) {
    const href = `tutorials/${entry.slug}/`;
    const nav = navByHref.get(href);
    entries.push({
      title: entry.data.title,
      description: nav?.description ?? entry.data.description,
      href: withBase(base, href),
      section: nav?.section ?? "Guides",
      content: normalizeMarkdown(entry.body),
    });
  }

  return new Response(JSON.stringify(entries), {
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "public, max-age=300",
    },
  });
}
