import type { MetadataRoute } from "next";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export default function sitemap(): MetadataRoute.Sitemap {
  return ["", "/privacidad"].map((p) => ({ url: `${SITE}${p}`, changeFrequency: "monthly" as const }));
}
