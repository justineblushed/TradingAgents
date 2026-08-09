import type { Metadata } from "next";
import "./globals.css";
import NavLinks from "./nav-links";

export const metadata: Metadata = {
  title: "Family Finance Tracker",
  description: "Local-first family finance and spending dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="mx-auto max-w-5xl px-4 py-6">
          <header className="mb-8 flex items-center justify-between">
            <h1 className="text-xl font-semibold text-brand-700">
              Family Finance Tracker
            </h1>
            <NavLinks />
          </header>
          <main>{children}</main>
        </div>
      </body>
    </html>
  );
}
