import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import { Providers } from "./providers";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Imputable",
  description:
    "Imputable - A system of record for engineering and product decisions",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ClerkProvider
      appearance={{
        elements: {
          formButtonPrimary: "bg-indigo-600 hover:bg-indigo-700 text-sm",
          card: "shadow-lg",
          headerTitle: "text-xl font-bold",
          headerSubtitle: "text-gray-600",
          socialButtonsBlockButton: "border-gray-300",
          formFieldInput: "border-gray-300 focus:ring-indigo-500",
          footerActionLink: "text-indigo-600 hover:text-indigo-700",
        },
      }}
    >
      <html lang="en" suppressHydrationWarning>
        <body className={`${inter.variable} font-sans antialiased`}>
          <Providers>{children}</Providers>
        </body>
      </html>
    </ClerkProvider>
  );
}
