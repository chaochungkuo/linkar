export type DocsNavItem = {
  title: string;
  href: string;
  description?: string;
};

export type DocsNavGroup = {
  title: string;
  description: string;
  items: DocsNavItem[];
};

export const docsNav: DocsNavGroup[] = [
  {
    title: "Getting Started",
    description: "Install Linkar, create a project, and run your first shared pack.",
    items: [
      {
        title: "Getting started",
        href: "tutorials/getting-started/",
        description: "Install Linkar, initialize a project, run a template, and inspect outputs.",
      },
      {
        title: "Packs and scope",
        href: "tutorials/packs-and-scope/",
        description: "Understand global packs, project packs, and explicit pack references.",
      },
      {
        title: "Managing Git-backed packs",
        href: "tutorials/managing-git-backed-packs/",
        description: "Update remote packs and switch between local and GitHub-backed sources.",
      },
    ],
  },
  {
    title: "Concepts",
    description: "Build the mental model: packs, projects, templates, bindings, and provenance.",
    items: [
      {
        title: "Why Linkar",
        href: "explanations/why-linkar/",
        description: "The problem Linkar solves and the constraints it optimizes for.",
      },
      {
        title: "Pack and project model",
        href: "explanations/pack-and-project-model/",
        description: "Why reusable assets and local work live in separate places.",
      },
      {
        title: "Template runtime contract",
        href: "explanations/template-runtime-contract/",
        description: "The `linkar_template.yaml` contract and render/run behavior.",
      },
      {
        title: "Params, bindings, and resolution",
        href: "explanations/params-bindings-and-resolution/",
        description: "How explicit params, defaults, and pack bindings interact.",
      },
      {
        title: "Project lifecycle",
        href: "explanations/project-lifecycle/",
        description: "Render, run, collect, clean, inspect, and prune in context.",
      },
      {
        title: "Project runs and metadata",
        href: "explanations/project-runs-and-metadata/",
        description: "What lives in `project.yaml` and under `.linkar/`.",
      },
      {
        title: "Reproducibility and versioning",
        href: "explanations/reproducibility-and-versioning/",
        description: "Pack revisions, run metadata, and update policy.",
      },
    ],
  },
  {
    title: "Guides",
    description: "Practical authoring and automation workflows.",
    items: [
      {
        title: "Build a real pack",
        href: "tutorials/build-a-real-pack/",
        description: "Create a useful pack with templates and bindings.",
      },
      {
        title: "Authoring script.sh templates",
        href: "tutorials/authoring-script-sh/",
        description: "Use shell entrypoints when local orchestration is still simple.",
      },
      {
        title: "Python entry and runtime metadata",
        href: "tutorials/python-entry-and-runtime-metadata/",
        description: "Move complex template logic into Python while keeping run scripts small.",
      },
      {
        title: "Testing basic templates",
        href: "tutorials/testing-basic-templates/",
        description: "Test template behavior and output contracts locally.",
      },
      {
        title: "Wrapping external pipelines",
        href: "tutorials/wrapping-external-pipelines/",
        description: "Turn external CLI workflows into inspectable Linkar templates.",
      },
      {
        title: "Using Linkar from agents",
        href: "tutorials/using-linkar-from-agents/",
        description: "Use the CLI, API, and MCP server from automation clients.",
      },
    ],
  },
  {
    title: "Reference",
    description: "Lookup material for APIs, interfaces, and advanced integrations.",
    items: [
      {
        title: "CLI, API, and MCP interfaces",
        href: "explanations/interfaces-and-automation/",
        description: "The shared runtime semantics across human and machine interfaces.",
      },
      {
        title: "Local API reference",
        href: "explanations/local-api-reference/",
        description: "HTTP endpoints and response conventions.",
      },
      {
        title: "Discovery layers and site packs",
        href: "explanations/discovery-layers-and-site-packs/",
        description: "How site-specific lookup logic belongs in packs.",
      },
      {
        title: "Example pack progression",
        href: "tutorials/example-pack-progression/",
        description: "Map bundled examples to the patterns they demonstrate.",
      },
    ],
  },
];

export function withBase(base: string, href: string): string {
  return `${base}${href}`;
}
