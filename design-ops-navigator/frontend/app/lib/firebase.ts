import { initializeApp, getApps } from "firebase/app";
import { getAuth, GoogleAuthProvider, signInWithPopup, signInWithEmailAndPassword, signOut as fbSignOut } from "firebase/auth";
import { getFirestore, doc, getDoc, setDoc, serverTimestamp } from "firebase/firestore";

const firebaseConfig = {
  apiKey:            process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain:        process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId:         process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket:     process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId:             process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

// Prevent duplicate initialization in Next.js dev hot-reload
const app = getApps().length ? getApps()[0] : initializeApp(firebaseConfig);

export const auth = getAuth(app);
export const db   = getFirestore(app);
export const googleProvider = new GoogleAuthProvider();

// ── User profile helpers ───────────────────────────────────────────────────────

export interface UserProfile {
  uid: string;
  email: string | null;
  displayName: string | null;
  photoURL: string | null;
  approved: boolean;
  role: "admin" | "beta" | "judge" | "waitlist";
  createdAt: unknown;
  lastLoginAt: unknown;
}

/**
 * Fetch the user profile doc. Returns null if it doesn't exist.
 */
export async function getUserProfile(uid: string): Promise<UserProfile | null> {
  const snap = await getDoc(doc(db, "users", uid));
  return snap.exists() ? (snap.data() as UserProfile) : null;
}

/**
 * Create or update the user profile doc on sign-in.
 * Only creates if it doesn't exist (preserves admin-set fields like role/approved).
 */
export async function upsertUserProfile(user: {
  uid: string;
  email: string | null;
  displayName: string | null;
  photoURL: string | null;
}): Promise<UserProfile> {
  const ref = doc(db, "users", user.uid);
  const snap = await getDoc(ref);

  if (!snap.exists()) {
    // New user — create with default approved=true for open beta
    const profile: Omit<UserProfile, "uid"> = {
      email: user.email,
      displayName: user.displayName,
      photoURL: user.photoURL,
      approved: true,   // Open beta: everyone gets in
      role: "beta",
      createdAt: serverTimestamp(),
      lastLoginAt: serverTimestamp(),
    };
    await setDoc(ref, profile);
    return { uid: user.uid, ...profile };
  }

  // Existing user — just update last login
  await setDoc(ref, { lastLoginAt: serverTimestamp() }, { merge: true });
  return { uid: user.uid, ...snap.data() } as UserProfile;
}

// ── Auth actions ──────────────────────────────────────────────────────────────

export async function signInWithGoogle() {
  const result = await signInWithPopup(auth, googleProvider);
  return result.user;
}

export async function signInWithEmail(email: string, password: string) {
  const result = await signInWithEmailAndPassword(auth, email, password);
  return result.user;
}

export async function signOut() {
  await fbSignOut(auth);
  // Clear the HttpOnly session cookie via the server route
  await fetch("/api/auth/session", { method: "DELETE" }).catch(() => {});
}
