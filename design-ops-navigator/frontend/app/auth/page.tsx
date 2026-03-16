"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { onAuthStateChanged, signOut } from "firebase/auth";
import { auth, db, signInWithGoogle, signInWithEmail, upsertUserProfile, getUserProfile } from "../lib/firebase";
import { collection, addDoc, serverTimestamp } from "firebase/firestore";
import { initStorage } from "../lib/storage";
import { Eye, BookOpen, Target, Layers, Zap } from "lucide-react";

// ── Google icon ───────────────────────────────────────────────────────────────

function GoogleIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 18 18" fill="none" aria-hidden="true">
      <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z" fill="#4285F4"/>
      <path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#34A853"/>
      <path d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" fill="#FBBC05"/>
      <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z" fill="#EA4335"/>
    </svg>
  );
}

// ── Feature list ──────────────────────────────────────────────────────────────

const FEATURES = [
  { Icon: Eye,      label: "Figma & live website critique" },
  { Icon: BookOpen, label: "Grounded in WCAG, Nielsen, Gestalt" },
  { Icon: Target,   label: "Severity scoring and issue tracking" },
  { Icon: Layers,   label: "Design system context awareness" },
  { Icon: Zap,      label: "Instant structured reports" },
] as const;

// ── Logo ──────────────────────────────────────────────────────────────────────

function Logo({ size = "md" }: { size?: "sm" | "md" }) {
  const box = size === "sm" ? "h-7 w-7" : "h-8 w-8";
  const icon = size === "sm" ? "h-3.5 w-3.5" : "h-4 w-4";
  const name = size === "sm" ? "text-[13px] font-semibold text-zinc-100 leading-tight" : "text-sm font-semibold text-zinc-100";
  const sub  = size === "sm" ? "text-[11px] text-zinc-600" : "text-xs text-zinc-500";
  return (
    <div className="flex items-center gap-3">
      <div className={`${box} rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shrink-0`}>
        <Eye className={`${icon} text-white`} />
      </div>
      <div>
        <p className={name}>Vera</p>
        <p className={sub}>Design Ops Agent</p>
      </div>
    </div>
  );
}

// ── Beta badge ────────────────────────────────────────────────────────────────

function BetaBadge() {
  return (
    <span className="inline-flex items-center rounded-md border border-indigo-800/40 bg-indigo-950/60 px-2 py-0.5 text-[11px] font-medium text-indigo-400">
      Beta
    </span>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AuthPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"google" | "email">("google");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [waitlistEmail, setWaitlistEmail] = useState("");
  const [waitlistDone, setWaitlistDone] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState(false);

  // If already authed, go straight to app (unless ?view=auth is set)
  useEffect(() => {
    const unsub = onAuthStateChanged(auth, (user) => {
      setCurrentUser(!!user);
      const viewAuth = new URLSearchParams(window.location.search).get("view") === "auth";
      if (user && !viewAuth) {
        router.replace("/");
      }
    });
    return unsub;
  }, [router]);

  async function handleGoogle() {
    setLoading(true);
    setError(null);
    try {
      const user = await signInWithGoogle();
      const profile = await upsertUserProfile({
        uid: user.uid,
        email: user.email,
        displayName: user.displayName,
        photoURL: user.photoURL,
      });
      if (profile.approved) {
        initStorage(user.uid);
        await fetch("/api/auth/session", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ uid: user.uid }),
        });
        router.replace("/");
      } else {
        setError("Your request is under review. You'll receive access shortly.");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Sign-in failed";
      if (msg.includes("popup-closed")) { setLoading(false); return; }
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  async function handleEmail(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const user = await signInWithEmail(email, password);
      const profile = await getUserProfile(user.uid);
      if (profile?.approved) {
        initStorage(user.uid);
        await fetch("/api/auth/session", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ uid: user.uid }),
        });
        router.replace("/");
      } else {
        setError("Access not yet granted for this account.");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Sign-in failed";
      if (msg.includes("invalid-credential") || msg.includes("wrong-password")) {
        setError("Incorrect email or password.");
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleWaitlist(e: React.FormEvent) {
    e.preventDefault();
    if (!waitlistEmail.includes("@")) return;
    try {
      await addDoc(collection(db, "waitlist"), {
        email: waitlistEmail,
        requestedAt: serverTimestamp(),
      });
    } catch { /* fail silently */ } finally {
      setWaitlistDone(true);
    }
  }

  async function handleSignOut() {
    setLoading(true);
    try {
      await signOut(auth);
      setCurrentUser(false);
      setError(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Sign-out failed";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-screen bg-zinc-950">

      {/* ── Mobile header (visible below lg breakpoint) ── */}
      <header className="lg:hidden border-b border-white/[0.06] px-6 h-[56px] flex items-center justify-between shrink-0">
        <Logo size="sm" />
        <div className="flex items-center gap-3">
          {currentUser && (
            <button
              onClick={handleSignOut}
              disabled={loading}
              className="text-xs text-zinc-500 hover:text-zinc-400 transition-colors disabled:opacity-50"
            >
              Sign out
            </button>
          )}
          <BetaBadge />
        </div>
      </header>

      {/* ── Split layout ── */}
      <main className="flex-1 flex min-h-0">

        {/* ── Left panel (desktop only) ── */}
        <div className="hidden lg:flex flex-col flex-1 justify-center px-16 py-12">
          <div className="max-w-md space-y-8">

            {/* Brand */}
            <Logo size="md" />

            {/* Headline */}
            <div className="space-y-3">
              <h1 className="text-2xl font-bold text-zinc-100 leading-tight">
                Expert UX Critique<br />
                <span className="text-zinc-400 font-semibold">Grounded in Research</span>
              </h1>
              <p className="text-sm text-zinc-500 leading-relaxed">
                Point Vera at any Figma frame or live website. Get structured critique
                citing WCAG, Nielsen, Gestalt, and cognitive principles — in seconds.
              </p>
            </div>

            {/* Feature list */}
            <ul className="space-y-3">
              {FEATURES.map(({ Icon, label }) => (
                <li key={label} className="flex items-center gap-3">
                  <Icon className="h-4 w-4 text-indigo-400 shrink-0" />
                  <span className="text-sm text-zinc-300">{label}</span>
                </li>
              ))}
            </ul>

            {/* Trust signal */}
            <p className="text-xs text-zinc-600">
              Built with Gemini 2.5 Flash · Google ADK · Firestore
            </p>

          </div>
        </div>

        {/* ── Right panel ── */}
        <div className="flex flex-col w-full lg:w-[420px] lg:border-l border-white/[0.06]">

          {/* Right panel desktop header */}
          <div className="hidden lg:flex border-b border-white/[0.06] px-6 h-[56px] items-center justify-between shrink-0">
            <Logo size="sm" />
            <div className="flex items-center gap-3">
              {currentUser && (
                <button
                  onClick={handleSignOut}
                  disabled={loading}
                  className="text-xs text-zinc-500 hover:text-zinc-400 transition-colors disabled:opacity-50"
                >
                  Sign out
                </button>
              )}
              <BetaBadge />
            </div>
          </div>

          {/* Form area — vertically centered */}
          <div className="flex-1 flex flex-col items-center justify-center px-8 py-12 overflow-y-auto">
            <div className="w-full max-w-[340px] space-y-3">

              {/* Sign-in card */}
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 space-y-5">

                {/* Card header */}
                <div>
                  <h2 className="text-base font-semibold text-zinc-100">Get Started</h2>
                  <p className="text-xs text-zinc-500 mt-1">Invite-only access. Already have credentials?</p>
                </div>

                {/* Google button */}
                <button
                  onClick={handleGoogle}
                  disabled={loading}
                  className="w-full flex items-center justify-center gap-2.5 rounded-xl border border-white/[0.07] bg-white/[0.03] px-4 py-2.5 text-sm font-medium text-zinc-100 hover:bg-white/[0.07] hover:border-white/[0.12] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <GoogleIcon />
                  {loading ? "Signing in…" : "Continue with Google"}
                </button>

                {/* OR divider */}
                <div className="flex items-center gap-3">
                  <div className="flex-1 h-px bg-white/[0.06]" />
                  <span className="text-[11px] text-zinc-600 font-medium">OR</span>
                  <div className="flex-1 h-px bg-white/[0.06]" />
                </div>

                {/* Email toggle or form */}
                {mode === "google" ? (
                  <button
                    onClick={() => { setMode("email"); setError(null); }}
                    className="w-full text-center text-xs text-indigo-400 hover:text-indigo-300 transition-colors py-1"
                  >
                    Sign in with email credentials →
                  </button>
                ) : (
                  <form onSubmit={handleEmail} className="space-y-3">
                    <input
                      type="email"
                      value={email}
                      onChange={e => setEmail(e.target.value)}
                      placeholder="Email"
                      required
                      autoComplete="email"
                      aria-label="Email"
                      className="w-full bg-zinc-900 border border-white/[0.07] rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-indigo-500/50 transition-colors"
                    />
                    <input
                      type="password"
                      value={password}
                      onChange={e => setPassword(e.target.value)}
                      placeholder="Password"
                      required
                      autoComplete="current-password"
                      className="w-full bg-zinc-900 border border-white/[0.07] rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-indigo-500/50 transition-colors"
                    />
                    <button
                      type="submit"
                      disabled={loading || !email || !password}
                      className="w-full rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                    >
                      {loading ? "Signing in…" : "Sign In"}
                    </button>
                    <button
                      type="button"
                      onClick={() => { setMode("google"); setError(null); }}
                      className="w-full text-center text-xs text-zinc-600 hover:text-zinc-400 transition-colors py-1"
                    >
                      ← Back to Google
                    </button>
                  </form>
                )}

                {/* Error state */}
                {error && (
                  <div className="rounded-lg border border-red-900/40 bg-red-950/20 px-4 py-3">
                    <p className="text-xs text-red-300 font-medium">{error}</p>
                  </div>
                )}

              </div>

              {/* Waitlist card */}
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                <p className="text-xs font-medium text-zinc-400 mb-3">Not invited yet?</p>
                {waitlistDone ? (
                  <p className="text-xs text-emerald-400 font-medium">
                    You&apos;re on the waitlist. We&apos;ll reach out soon.
                  </p>
                ) : (
                  <form onSubmit={handleWaitlist} className="flex gap-2">
                    <input
                      type="email"
                      value={waitlistEmail}
                      onChange={e => setWaitlistEmail(e.target.value)}
                      placeholder="your@email.com"
                      required
                      autoComplete="email"
                      className="flex-1 min-w-0 bg-zinc-900 border border-white/[0.07] rounded-lg px-3 py-2 text-xs text-zinc-300 placeholder-zinc-600 focus:outline-none focus:border-indigo-500/50 transition-colors"
                    />
                    <button
                      type="submit"
                      className="shrink-0 rounded-lg border border-indigo-800/40 bg-indigo-950/60 px-3 py-2 text-xs font-medium text-indigo-400 hover:bg-indigo-950 transition-colors"
                    >
                      Join
                    </button>
                  </form>
                )}
              </div>

            </div>
          </div>
        </div>

      </main>
    </div>
  );
}
