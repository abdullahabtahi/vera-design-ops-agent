import { NextResponse } from "next/server";

// Waitlist writes go directly to Firestore from the client (firebase.ts).
// This endpoint exists as a fallback / for non-browser contexts.
export async function POST(request: Request) {
  try {
    const { email } = await request.json();
    if (!email || !email.includes("@")) {
      return NextResponse.json({ error: "Invalid email" }, { status: 400 });
    }
    // Forward to Python backend which has Firestore admin access
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
    await fetch(`${backendUrl}/api/waitlist`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    }).catch(() => {}); // fail silently
    return NextResponse.json({ ok: true });
  } catch {
    return NextResponse.json({ ok: true }); // always succeed for UX
  }
}
