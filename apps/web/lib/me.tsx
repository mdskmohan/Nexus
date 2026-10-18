"use client";

import { createContext, useContext } from "react";
import type { Me } from "./api";

export const MeContext = createContext<Me | null>(null);
// Reloads who is signed in, after they change their name or the workspace's.
export const RefreshMeContext = createContext<() => Promise<void>>(async () => {});

export function useRefreshMe() {
  return useContext(RefreshMeContext);
}

export function useMe(): Me {
  const me = useContext(MeContext);
  if (!me) throw new Error("useMe outside the signed-in app");
  return me;
}
