export const site = {
  name: "Dex Trove",
  tagline: "A trove of dexterities for your agents",
  description:
    "Dex Trove (Dexterity Trove): skills, agents, instructions, hooks and plugins your AI can pick up, learned from the best open repos, licence-checked item by item, credited to their authors and one command away.",
  repo: "https://github.com/Neo-Pragnya/Dex-Trove",
  pypi: "https://pypi.org/project/dex-trove/",
} as const;

export type Kind = "skill" | "agent" | "instruction" | "prompt" | "hook" | "workflow" | "plugin";

export const KINDS: Record<Kind, { label: string; plural: string; blurb: string; ananke: string }> = {
  skill: {
    label: "Skill",
    plural: "Skills",
    blurb: "Folders with a SKILL.md and bundled scripts or references.",
    ananke: "skill",
  },
  agent: {
    label: "Agent",
    plural: "Agents",
    blurb: "Specialised agent personas with their own instructions.",
    ananke: "agent",
  },
  instruction: {
    label: "Instruction",
    plural: "Instructions",
    blurb: "Coding standards applied to matching files.",
    ananke: "prompt",
  },
  prompt: { label: "Prompt", plural: "Prompts", blurb: "Reusable prompt files.", ananke: "prompt" },
  hook: {
    label: "Hook",
    plural: "Hooks",
    blurb: "Event-triggered automations (they run code).",
    ananke: "tool",
  },
  workflow: {
    label: "Workflow",
    plural: "Workflows",
    blurb: "Agentic workflows for repository automation.",
    ananke: "workflow",
  },
  plugin: {
    label: "Plugin",
    plural: "Plugins",
    blurb: "Bundles of related skills and agents.",
    ananke: "bundle",
  },
};

export const KIND_ORDER = Object.keys(KINDS) as Kind[];

/** The shape language: every kind has a calm rest shape that morphs into a lively one on hover. */
export const KIND_GLYPH: Record<Kind, string> = {
  skill: "blob>star",
  agent: "circle>flower",
  instruction: "squircle>square",
  prompt: "triangle>circle",
  hook: "diamond>spark",
  workflow: "hex>blob2",
  plugin: "octagon>flower8",
};

/** Native install targets per kind (mirrors dex_trove/install.py). */
export const TARGETS: Record<Kind, string[]> = {
  skill: ["claude", "copilot"],
  agent: ["claude", "copilot"],
  instruction: ["copilot"],
  prompt: ["claude", "copilot"],
  hook: ["copilot"],
  workflow: ["copilot"],
  plugin: ["claude", "copilot"],
};

export function itemHref(base: string, kind: string, ns: string, name: string): string {
  return `${base}${kind}/${ns}.${name}/`;
}

/** "skill:awesome-copilot/foo" → href */
export function memberHref(base: string, member: string): string {
  const [kind, rest] = member.split(":");
  const [ns, name] = (rest ?? "").split("/");
  return itemHref(base, kind ?? "skill", ns ?? "", name ?? "");
}

export function shortCommit(commit?: string | null): string {
  return commit ? commit.slice(0, 7) : "local";
}

/** Documentation sidebar: section → doc ids (paths under docs/ without .md). */
export const DOC_NAV: { section: string; items: string[]; shapes: string; tint: string }[] = [
  { section: "Overview", items: ["index"], shapes: "blob>star", tint: "coral" },
  {
    section: "Concepts",
    shapes: "circle>flower",
    tint: "teal",
    items: [
      "concepts/why-dex-trove",
      "concepts/architecture",
      "concepts/artifact-kinds",
      "concepts/licence-policy",
      "concepts/provenance-and-versioning",
      "concepts/security-model",
    ],
  },
  {
    section: "Guides",
    shapes: "squircle>spark",
    tint: "lilac",
    items: [
      "guides/getting-started",
      "guides/installing-items",
      "guides/ananke-integration",
      "guides/adding-a-source",
      "guides/first-party-skills",
      "guides/docs-site",
      "guides/release",
    ],
  },
  {
    section: "Reference",
    shapes: "hex>flower8",
    tint: "lemon",
    items: [
      "reference/cli",
      "reference/sources-yaml",
      "reference/item-format",
      "reference/trove-files",
      "reference/licence-identification",
      "reference/exclusion-reasons",
      "reference/configuration",
      "reference/python-api",
    ],
  },
  { section: "Design", items: ["design/DESIGN", "design/CHECKLIST"], shapes: "octagon>gear", tint: "pink" },
];

/** Sidebar labels for docs without `title` frontmatter (kept frontmatter-free so GitHub renders them cleanly). */
export const DOC_TITLES: Record<string, string> = {
  "design/DESIGN": "Design document",
  "design/CHECKLIST": "Implementation checklist",
};

export function docHref(base: string, id: string): string {
  return id === "index" ? `${base}docs/` : `${base}docs/${id}/`;
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

/** "skill:awesome-copilot/foo" → { kind, ns, name } */
export function parseRef(ref: string): { kind: string; ns: string; name: string } {
  const [kind = "skill", rest = ""] = ref.split(":");
  const [ns = "", name = ""] = rest.split("/");
  return { kind, ns, name };
}
