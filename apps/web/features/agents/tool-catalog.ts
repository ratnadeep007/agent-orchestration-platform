export type BuiltInTool = {
  description: string;
  name: string;
  title: string;
};

export const BUILTIN_TOOLS: BuiltInTool[] = [
  {
    name: "current_time",
    title: "Current time",
    description: "Get the current UTC date and time.",
  },
  {
    name: "recent_messages",
    title: "Recent messages",
    description: "Load the latest messages from the active workflow run.",
  },
  {
    name: "search_messages",
    title: "Search messages",
    description: "Search the active workflow run message history by text.",
  },
  {
    name: "web_search",
    title: "Web search",
    description: "Search the web through Firecrawl and return crawled results.",
  },
];

export const BUILTIN_TOOL_NAMES = BUILTIN_TOOLS.map((tool) => tool.name);
