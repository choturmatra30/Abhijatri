/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
  readonly VITE_DEFAULT_TIMEZONE?: string;
  readonly VITE_ALLOWED_BACKEND_HOSTS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

