import http from "node:http";
import { readFile, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const distDir = path.join(__dirname, "dist", "server");
const clientDir = path.join(__dirname, "dist", "client");

const serverModule = await import(pathToFileURL(path.join(distDir, "index.js")).href);
const worker = serverModule.default ?? serverModule;

const mimeTypes = {
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".map": "application/json; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
};

function toResponseHeaders(headers = {}) {
  const out = new Headers();
  for (const [key, value] of Object.entries(headers)) {
    if (value == null) continue;
    if (Array.isArray(value)) {
      for (const item of value) out.append(key, String(item));
    } else {
      out.set(key, String(value));
    }
  }
  return out;
}

async function serveStatic(reqUrl, res) {
  const url = new URL(reqUrl, "http://127.0.0.1");
  const pathname = decodeURIComponent(url.pathname);
  const directPath = path.join(clientDir, pathname);
  const candidates = [
    directPath,
    `${directPath}.js`,
    `${directPath}.css`,
    path.join(clientDir, "assets", path.basename(pathname)),
  ];

  for (const candidate of candidates) {
    try {
      const s = await stat(candidate);
      if (!s.isFile()) continue;
      const bytes = await readFile(candidate);
      const ext = path.extname(candidate).toLowerCase();
      res.writeHead(200, { "Content-Type": mimeTypes[ext] ?? "application/octet-stream" });
      res.end(bytes);
      return true;
    } catch {
      continue;
    }
  }

  return false;
}

const port = Number(process.env.PORT || 5183);
const host = process.env.HOST || "127.0.0.1";

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url ?? "/", `http://${req.headers.host || `${host}:${port}`}`);
    const response = await worker.fetch(
      new Request(url, {
        method: req.method,
        headers: toResponseHeaders(req.headers),
        body: ["GET", "HEAD"].includes(req.method ?? "GET") ? undefined : req,
        duplex: "half",
      }),
      {},
      {},
    );

    if (response.status === 404 && (req.method === "GET" || req.method === "HEAD")) {
      const served = await serveStatic(url.toString(), res);
      if (served) return;
    }

    res.writeHead(response.status, Object.fromEntries(response.headers.entries()));
    if (req.method === "HEAD") {
      res.end();
      return;
    }
    const arrayBuffer = await response.arrayBuffer();
    res.end(Buffer.from(arrayBuffer));
  } catch (error) {
    res.writeHead(500, { "Content-Type": "text/plain; charset=utf-8" });
    res.end(error instanceof Error ? (error.stack ?? error.message) : String(error));
  }
});

server.listen(port, host, () => {
  console.log(`GeoRaster frontend served at http://${host}:${port}/map`);
});
