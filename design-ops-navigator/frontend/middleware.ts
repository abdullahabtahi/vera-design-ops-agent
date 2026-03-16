import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Routes that don't require auth
const PUBLIC = ["/auth", "/api/waitlist", "/api/auth/session"];

// Local dev bypass: set AUTH_BYPASS=true in .env.local to skip auth entirely
const AUTH_BYPASS = process.env.NEXT_PUBLIC_AUTH_BYPASS === "true";

export function middleware(request: NextRequest) {
  if (AUTH_BYPASS) return NextResponse.next();

  const { pathname } = request.nextUrl;

  // Allow public routes and Next.js internals
  if (PUBLIC.some(p => pathname.startsWith(p))) return NextResponse.next();

  // Check for the HttpOnly session cookie set by /api/auth/session after Firebase sign-in
  const uid = request.cookies.get("don_session")?.value;
  if (!uid) {
    const url = request.nextUrl.clone();
    url.pathname = "/auth";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|ico)$).*)"],
};
