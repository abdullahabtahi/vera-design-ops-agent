import { NextRequest, NextResponse } from "next/server";

const IS_PROD = process.env.NODE_ENV === "production";
const COOKIE_NAME = "don_session";
// 30 days
const MAX_AGE = 60 * 60 * 24 * 30;

/**
 * POST /api/auth/session
 * Body: { uid: string }
 * Sets an HttpOnly; Secure; SameSite=Strict session cookie containing the UID.
 * Called client-side after Firebase sign-in succeeds.
 */
export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => null);
  const uid = typeof body?.uid === "string" ? body.uid.trim() : "";

  if (!uid || uid.length > 128) {
    return NextResponse.json({ error: "Invalid uid" }, { status: 400 });
  }

  const res = NextResponse.json({ ok: true });
  res.cookies.set(COOKIE_NAME, uid, {
    httpOnly: true,
    secure: IS_PROD,
    sameSite: "strict",
    path: "/",
    maxAge: MAX_AGE,
  });
  return res;
}

/**
 * DELETE /api/auth/session
 * Clears the session cookie on sign-out.
 */
export async function DELETE() {
  const res = NextResponse.json({ ok: true });
  res.cookies.set(COOKIE_NAME, "", {
    httpOnly: true,
    secure: IS_PROD,
    sameSite: "strict",
    path: "/",
    maxAge: 0,
  });
  return res;
}
