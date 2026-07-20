import { createContext, useContext, type ReactNode } from "react";

import type { NanobotClient } from "@/lib/nanobot-client";
import type { WebUIIngressLimits, UserInfo } from "@/lib/types";

interface ClientContextValue {
  client: NanobotClient;
  token: string;
  modelName: string | null;
  ingressLimits: WebUIIngressLimits | null;
  user: UserInfo | null;
}

const ClientContext = createContext<ClientContextValue | null>(null);

export function ClientProvider({
  client,
  token,
  modelName = null,
  ingressLimits = null,
  user = null,
  children,
}: {
  client: NanobotClient;
  token: string;
  modelName?: string | null;
  ingressLimits?: WebUIIngressLimits | null;
  user?: UserInfo | null;
  children: ReactNode;
}) {
  return (
    <ClientContext.Provider value={{ client, token, modelName, ingressLimits, user }}>
      {children}
    </ClientContext.Provider>
  );
}

export function useClient(): ClientContextValue {
  const ctx = useContext(ClientContext);
  if (!ctx) {
    throw new Error("useClient must be used within a ClientProvider");
  }
  return ctx;
}
