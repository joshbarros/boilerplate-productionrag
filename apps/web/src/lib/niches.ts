// Niche registry — wire up new niches here.
//
// Each niche has a unique key, display name, and backend URL.
// The web app's niche switcher reads from this list.
//
// In dev, each niche runs on its own port:
//   core (generic RAG)        : http://localhost:8800
//   medical (PubMed Central)   : http://localhost:8810
//   legal   (CourtListener)     : http://localhost:8820  (future)
//   accounting (SEC EDGAR)     : http://localhost:8830  (future)
//
// NEXT_PUBLIC_NICHES is a JSON-encoded array. We keep it in env (not
// hardcoded) so each deployment can pick which niches to enable
// without rebuilding the bundle.

export type Niche = {
  key: string; // "medical"
  label: string; // "Medical"
  backend: string; // "http://localhost:8810"
  enabled: boolean;
  description?: string;
};

const RAW: string = process.env.NEXT_PUBLIC_NICHES ?? "";

export const NICHES: Niche[] = (() => {
  if (!RAW) {
    // Default dev fixtures — overridden via env in prod
    return [
      {
        key: "core",
        label: "Generic",
        backend: "/api/backend", // proxied → http://localhost:8800
        enabled: true,
        description: "Default RAG engine",
      },
      {
        key: "medical",
        label: "Medical",
        backend: "http://localhost:8810",
        enabled: true,
        description: "PubMed Central literature",
      },
    ];
  }
  try {
    return JSON.parse(RAW) as Niche[];
  } catch {
    return [];
  }
})();

export const DEFAULT_NICHE = NICHES[0]?.key ?? "core";
