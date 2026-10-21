import { Message } from "@langchain/langgraph-sdk";

const SELECTED_MODEL_HEADER = "x-model-router-selected-model";
const MODEL_QUERY_PARAM = "blockyModels";

export interface ModelDisplay {
  routingModel: string;
  name: string;
  primaryColor: string;
}

export function routedModelOf(message: Message): string | null {
  const metadata = (
    message as Message & {
      response_metadata?: {
        headers?: Record<string, unknown>;
      };
    }
  ).response_metadata;
  const selectedModel = metadata?.headers?.[SELECTED_MODEL_HEADER];
  return typeof selectedModel === "string" ? selectedModel : null;
}

let cachedModels: ModelDisplay[] | null = null;

/** The models the SPA put on the iframe URL. Fixed for the life of the page. */
function blockyModels(): ModelDisplay[] {
  if (typeof window === "undefined") return [];
  if (cachedModels) return cachedModels;

  try {
    const encodedModels = new URLSearchParams(window.location.search).get(
      MODEL_QUERY_PARAM
    );
    const models = encodedModels ? JSON.parse(encodedModels) : null;
    cachedModels = Array.isArray(models) ? (models as ModelDisplay[]) : [];
  } catch {
    cachedModels = [];
  }
  return cachedModels;
}

export function modelDisplayFor(
  routedModel: string | null
): ModelDisplay | null {
  if (!routedModel) return null;
  return (
    blockyModels().find(
      (model) =>
        model &&
        typeof model.routingModel === "string" &&
        model.routingModel === routedModel &&
        typeof model.name === "string" &&
        typeof model.primaryColor === "string"
    ) ?? null
  );
}

/**
 * Whether to hold the model label and rail gutter open before the routing
 * header arrives. The SPA always supplies at least one model for a built agent.
 */
export function railGutterReserved(): boolean {
  return blockyModels().length > 0;
}
