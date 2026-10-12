import type { KnowledgeCategory } from "@/types/api";

export const knowledgeCategoryLabels: Record<KnowledgeCategory, string> = {
  FAQ: "FAQ",
  PRODUCT: "Product information",
  POLICY: "Policy",
  COMPANY: "Company information",
  OTHER: "Other",
};

export const knowledgeCategoryHints: Record<KnowledgeCategory, string> = {
  FAQ: "A common customer question and its answer.",
  PRODUCT: "Plans, pricing, features, and limits.",
  POLICY: "Refunds, terms, support hours, and other rules.",
  COMPANY: "Who you are, locations, and contact details.",
  OTHER: "Anything else the AI may rely on when drafting replies.",
};

export const KNOWLEDGE_TITLE_MAX = 200;
export const KNOWLEDGE_CONTENT_MAX = 8000;
