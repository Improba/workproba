 

declare namespace NodeJS {
  interface ProcessEnv {
    NODE_ENV: string;
    VUE_ROUTER_MODE: 'hash' | 'history' | 'abstract' | undefined;
    VUE_ROUTER_BASE: string | undefined;
    AI_SIDECAR_URL?: string;
    DESKTOP_INTERNAL_SECRET?: string;
    DESKTOP_MODE?: string;
  }
}
