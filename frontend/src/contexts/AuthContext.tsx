"use client";

/**
 * Firebase Authentication Context
 *
 * Provides auth state and functions throughout the app
 * Uses lazy initialization to work during SSR/build
 */

import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
} from "react";
import {
  auth as getAuth,
  onAuthStateChanged,
  signInWithEmail,
  signUpWithEmail,
  signInWithGoogle,
  logOut,
  getIdToken,
  User,
} from "@/lib/firebase";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (
    email: string,
    password: string,
    displayName?: string,
  ) => Promise<void>;
  signInGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
  getToken: () => Promise<string | null>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Only run on client side
    if (typeof window === "undefined") {
      setLoading(false);
      return;
    }

    const auth = getAuth();
    if (!auth) {
      // Firebase not available (missing config)
      setLoading(false);
      return;
    }

    const unsubscribe = onAuthStateChanged(auth, (user) => {
      setUser(user);
      setLoading(false);
    });

    return () => unsubscribe();
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    await signInWithEmail(email, password);
  }, []);

  const signUp = useCallback(
    async (email: string, password: string, displayName?: string) => {
      await signUpWithEmail(email, password, displayName);
    },
    [],
  );

  const signInGoogle = useCallback(async () => {
    await signInWithGoogle();
  }, []);

  const handleSignOut = useCallback(async () => {
    await logOut();
  }, []);

  const getToken = useCallback(async () => {
    return getIdToken();
  }, []);

  const value: AuthContextType = {
    user,
    loading,
    signIn,
    signUp,
    signInGoogle,
    signOut: handleSignOut,
    getToken,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

// Convenience hooks for common checks
export function useIsSignedIn() {
  const { user, loading } = useAuth();
  return { isSignedIn: !!user, loading };
}
