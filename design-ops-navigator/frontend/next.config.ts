import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";
const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

// Firebase Auth/Firestore endpoints the client SDK calls directly
const firebaseSrc = [
  "https://identitytoolkit.googleapis.com", // Firebase Auth REST API
  "https://securetoken.googleapis.com",      // ID token refresh
  "https://firestore.googleapis.com",        // Firestore gRPC-web
  "https://www.googleapis.com",             // misc Firebase SDK calls
].join(" ");

// connect-src: allow backend + localhost variants in dev + Firebase always
const connectSrc = isDev
  ? `'self' ${backendUrl} http://localhost:8000 http://127.0.0.1:8000 ${firebaseSrc}`
  : `'self' ${backendUrl} ${firebaseSrc}`;

// img-src: object URLs (critique images), data URIs (base64 previews), Figma CDN
const imgSrc = "img-src 'self' blob: data: https://www.figma.com https://figma-alpha-api.s3.us-west-2.amazonaws.com";

const csp = [
  "default-src 'self'",
  // Next.js requires 'unsafe-inline' for chunk loading; 'unsafe-eval' only needed in dev HMR
  // apis.google.com is required for Firebase Google Sign-In popup
  `script-src 'self' 'unsafe-inline' https://apis.google.com${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'", // Tailwind inlines styles
  imgSrc,
  `connect-src ${connectSrc} https://accounts.google.com`,
  "font-src 'self'",
  // accounts.google.com required for Google OAuth popup iframe
  "frame-src https://accounts.google.com",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const securityHeaders = [
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  { key: "Content-Security-Policy", value: csp },
  // HSTS only in production (HTTPS) — never in local dev over HTTP
  ...(isDev
    ? []
    : [{ key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" }]),
];

const nextConfig: NextConfig = {
  output: "standalone", // required for Cloud Run Docker deployment
  async headers() {
    return [{ source: "/(.*)", headers: securityHeaders }];
  },
};

export default nextConfig;
