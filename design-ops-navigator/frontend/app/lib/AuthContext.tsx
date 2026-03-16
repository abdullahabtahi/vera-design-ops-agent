"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { onAuthStateChanged, User } from "firebase/auth";
import { auth, getUserProfile, upsertUserProfile, signOut } from "./firebase";
import { initStorage } from "./storage";

interface AuthState {
  user: User | null;
  uid: string | null;
  loading: boolean;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  user: null,
  uid: null,
  loading: true,
  signOut: async () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [uid, setUid] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      if (firebaseUser) {
        // Upsert profile (creates on first sign-in, updates lastLogin on subsequent)
        await upsertUserProfile({
          uid: firebaseUser.uid,
          email: firebaseUser.email,
          displayName: firebaseUser.displayName,
          photoURL: firebaseUser.photoURL,
        });

        // Check approval status
        const profile = await getUserProfile(firebaseUser.uid);
        if (profile?.approved) {
          // Initialize namespaced storage for this user
          initStorage(firebaseUser.uid);

          // Set HttpOnly session cookie via server route (what middleware checks)
          await fetch("/api/auth/session", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ uid: firebaseUser.uid }),
          }).catch(() => {});

          setUser(firebaseUser);
          setUid(firebaseUser.uid);
        } else {
          // User exists but not approved — treat as signed out for app routing
          setUser(null);
          setUid(null);
          initStorage(null);
        }
      } else {
        setUser(null);
        setUid(null);
        initStorage(null);
      }
      setLoading(false);
    });

    return unsubscribe;
  }, []);

  return (
    <AuthContext.Provider value={{ user, uid, loading, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}
