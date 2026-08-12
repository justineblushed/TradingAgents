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
        <div className="flex min-h-screen">
          <aside className="flex w-60 shrink-0 flex-col border-r border-slate-200 bg-white px-3 py-6">
            <h1 className="mb-6 px-3 text-lg font-semibold text-brand-700">
              Family Finance
              <br />
              Tracker
            </h1>
            <NavLinks />
          </aside>
          <main className="min-w-0 flex-1 overflow-x-auto px-6 py-6">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
