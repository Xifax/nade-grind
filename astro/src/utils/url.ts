export function withBase(path: string = ""): string {
  if (!path) return import.meta.env.BASE_URL;

  const base = import.meta.env.BASE_URL.endsWith("/")
    ? import.meta.env.BASE_URL
    : import.meta.env.BASE_URL + "/";

  // ensure no double slashes
  const cleanPath = path.replace(/^\/+/, "");
  return base + cleanPath;
}
