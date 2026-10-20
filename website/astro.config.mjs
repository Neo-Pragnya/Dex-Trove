import { defineConfig } from "astro/config";
import { unified } from "@astrojs/markdown-remark";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import process from "node:process";
import { remarkDocLinks } from "./src/lib/remark-doc-links";
import { remarkCallouts } from "./src/lib/remark-callouts";

const site = "https://neo-pragnya.github.io";
const base = process.env.SITE_BASE ?? "/";

// Item pages render upstream Markdown we don't control: always sanitise. Heading ids are kept as-is
// (no "user-content-" prefix) so the on-page table of contents links resolve.
const sanitizeSchema = {
  ...defaultSchema,
  clobberPrefix: "",
  attributes: {
    ...defaultSchema.attributes,
    blockquote: [...(defaultSchema.attributes?.blockquote ?? []), ["className", /^callout(-[a-z]+)?$/]],
  },
};

export default defineConfig({
  site,
  base,
  trailingSlash: "always",
  markdown: {
    processor: unified({
      remarkPlugins: [remarkDocLinks, remarkCallouts],
      rehypePlugins: [[rehypeSanitize, sanitizeSchema]],
    }),
  },
});
