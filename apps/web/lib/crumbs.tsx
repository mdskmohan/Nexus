"use client";

import { createContext, useContext, useEffect, useState } from "react";

type Crumbs = { labels: Record<string, string>; set: (path: string, label: string | null) => void };

const CrumbContext = createContext<Crumbs>({ labels: {}, set: () => {} });

/** Lets a page name its own breadcrumb (a connection's label instead of its id). */
export function CrumbProvider({ children }: { children: React.ReactNode }) {
  const [labels, setLabels] = useState<Record<string, string>>({});
  const set = (path: string, label: string | null) =>
    setLabels((all) => {
      if ((all[path] ?? null) === label) return all;
      const next = { ...all };
      if (label === null) delete next[path]; else next[path] = label;
      return next;
    });
  return <CrumbContext.Provider value={{ labels, set }}>{children}</CrumbContext.Provider>;
}

export function useCrumbLabels() {
  return useContext(CrumbContext).labels;
}

export function useCrumb(path: string, label: string | null | undefined) {
  const { set } = useContext(CrumbContext);
  useEffect(() => {
    if (!label) return;
    set(path, label);
    return () => set(path, null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, label]);
}
