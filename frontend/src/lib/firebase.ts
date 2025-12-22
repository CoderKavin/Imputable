/**
 * Firebase Client Configuration
 *
 * Initialize Firebase for client-side authentication
 * Uses lazy initialization to prevent errors during SSR/build
 */

import { initializeApp, getApps, FirebaseApp } from "firebase/app";
import {
  getAuth,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  GoogleAuthProvider,
  signOut,
  onAuthStateChanged,
  User,
  updateProfile,
  Auth,
} from "firebase/auth";

// Firebase configuration from environment variables
const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

// Lazy initialization variables
let app: FirebaseApp | null = null;
let auth: Auth | null = null;
let googleProvider: GoogleAuthProvider | null = null;

/**
 * Check if Firebase can be initialized
 * Returns false during SSR or if API key is missing
 */
function canInitializeFirebase(): boolean {
  return typeof window !== "undefined" && !!firebaseConfig.apiKey;
}

/**
 * Get or initialize the Firebase app
 */
function getFirebaseApp(): FirebaseApp | null {
  if (!canInitializeFirebase()) {
    return null;
  }

  if (!app) {
    app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0];
  }
  return app;
}

/**
 * Get or initialize Firebase Auth
 */
function getFirebaseAuth(): Auth | null {
  const firebaseApp = getFirebaseApp();
  if (!firebaseApp) {
    return null;
  }

  if (!auth) {
    auth = getAuth(firebaseApp);
  }
  return auth;
}

/**
 * Get or initialize Google Auth Provider
 */
function getGoogleProvider(): GoogleAuthProvider | null {
  if (!canInitializeFirebase()) {
    return null;
  }

  if (!googleProvider) {
    googleProvider = new GoogleAuthProvider();
  }
  return googleProvider;
}

// Auth functions
export async function signInWithEmail(email: string, password: string) {
  const authInstance = getFirebaseAuth();
  if (!authInstance) {
    throw new Error("Firebase Auth not available");
  }
  return signInWithEmailAndPassword(authInstance, email, password);
}

export async function signUpWithEmail(
  email: string,
  password: string,
  displayName?: string,
) {
  const authInstance = getFirebaseAuth();
  if (!authInstance) {
    throw new Error("Firebase Auth not available");
  }
  const result = await createUserWithEmailAndPassword(
    authInstance,
    email,
    password,
  );
  if (displayName && result.user) {
    await updateProfile(result.user, { displayName });
  }
  return result;
}

export async function signInWithGoogle() {
  const authInstance = getFirebaseAuth();
  const provider = getGoogleProvider();
  if (!authInstance || !provider) {
    throw new Error("Firebase Auth not available");
  }
  return signInWithPopup(authInstance, provider);
}

export async function logOut() {
  const authInstance = getFirebaseAuth();
  if (!authInstance) {
    throw new Error("Firebase Auth not available");
  }
  return signOut(authInstance);
}

export async function getIdToken(): Promise<string | null> {
  const authInstance = getFirebaseAuth();
  if (!authInstance) return null;
  const user = authInstance.currentUser;
  if (!user) return null;
  return user.getIdToken();
}

/**
 * Export auth getter for components that need direct access
 * Returns null during SSR or if Firebase isn't initialized
 */
export { getFirebaseAuth as auth, onAuthStateChanged };
export type { User };
