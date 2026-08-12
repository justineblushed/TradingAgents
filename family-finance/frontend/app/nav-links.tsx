"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const PRIMARY_LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/cash-flow", label: "Cash Flow" },
  { href: "/health", label: "Health" },
  { href: "/net-worth", label: "Net Worth" },
  { href: "/transactions", label: "Transactions" },
  { href: "/payroll", label: "Payroll" },
];

// Setup/cleanup tools rather than day-to-day pages — grouped together so
// they don't compete for attention with the pages actually used day to day.
const ADMIN_LINKS = [
  { href: "/categories", label: "Categories" },
  { href: "/rules", label: "Rules" },
  { href: "/sign-check", label: "Sign Check" },
  { href: "/duplicates", label: "Duplicates" },
  { href: "/statement-log", label: "Statement Log" },
  { href: "/upload", label: "+ Upload Statement" },
];

function linkClass(active: boolean) {
  return `rounded-md px-3 py-2 ${
    active
      ? "bg-brand-600 font-semibold text-white shadow-sm"
      : "text-slate-600 hover:bg-slate-100 hover:text-brand-600"
  }`;
}

export default function NavLinks() {
  const pathname = usePathname();
  const isAdminRoute = ADMIN_LINKS.some((link) => link.href === pathname);
  const [adminOpen, setAdminOpen] = useState(isAdminRoute);

  return (
    <nav className="flex flex-col gap-1 text-sm font-medium">
      {PRIMARY_LINKS.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          aria-current={pathname === link.href ? "page" : undefined}
          className={linkClass(pathname === link.href)}
        >
          {link.label}
        </Link>
      ))}

      <button
        onClick={() => setAdminOpen((v) => !v)}
        aria-expanded={adminOpen}
        className="mt-2 flex items-center justify-between rounded-md px-3 py-2 text-slate-500 hover:bg-slate-100 hover:text-brand-600"
      >
        Admin
        <span className={`transition-transform ${adminOpen ? "rotate-90" : ""}`}>›</span>
      </button>
      {adminOpen && (
        <div className="ml-2 flex flex-col gap-1 border-l border-slate-200 pl-2">
          {ADMIN_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              aria-current={pathname === link.href ? "page" : undefined}
              className={linkClass(pathname === link.href)}
            >
              {link.label}
            </Link>
          ))}
        </div>
      )}
    </nav>
  );
}
