import type { NextRequest } from "next/server";

// Server-side proxy: the browser talks to this origin only; BACKEND_URL and API_KEY never reach the client.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";
const KEY = process.env.API_KEY;
const PASS = ["content-type", "content-disposition", "retry-after"];

async function forward(req: NextRequest, { params }: { params: { path: string[] } }) {
  const target = `${BACKEND}/api/v1/${params.path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;
  const headers: Record<string, string> = {};
  const ct = req.headers.get("content-type");
  if (ct) headers["content-type"] = ct;
  if (KEY) headers["x-api-key"] = KEY;
  let upstream: Response;
  try {
    upstream = await fetch(target, { method: req.method, headers, body: req.method === "GET" ? undefined : await req.arrayBuffer(), cache: "no-store" });
  } catch {
    return Response.json({ detail: "Backend no disponible" }, { status: 502 });
  }
  const out = new Headers({ "cache-control": "no-store" });
  PASS.forEach((h) => { const v = upstream.headers.get(h); if (v) out.set(h, v); });
  return new Response(upstream.body, { status: upstream.status, headers: out });
}

export { forward as GET, forward as POST };
