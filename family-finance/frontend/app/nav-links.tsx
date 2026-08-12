"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/cash-flow", label: "Cash Flow" },
  { href: "/calendar", label: "Calendar" },
  { href: "/health", label: "Health" },
  { href: "/net-worth", label: "Net Worth" },
  { href: "/transactions", label: "Transactions" },
  { href: "/payroll", label: "Payroll" },
  { href: "/categories", label: "Categories" },
  { href: "/rules", label: "Rules" },
  { href: "/sign-check", label: "Sign Check" },
  { href: "/duplicates", label: "Duplicates" },
  { href: "/statement-log", label: "Statement Log" },
];

export default function NavLinks() {
  const pathname = usePathname();
  return (
    <nav className="flex flex-col gap-1 text-sm font-medium">
      <Link
        href="/upload"
        aria-current={pathname === "/upload" ? "page" : undefined}
        className={`mb-2 rounded-md px-3 py-2 text-center font-medium text-white shadow-sm ${
          pathname === "/upload"
            ? "bg-brand-700"
            : "bg-brand-500 hover:bg-brand-600"
        }`}
      >
        + Upload Statement
      </Link>
      {LINKS.map((link) => {
        const active = pathname === link.href;
        return (
          <Link
            key={link.href}
            href={link.href}
            aria-current={active ? "page" : undefined}
            className={`rounded-md px-3 py-2 ${
              active
                ? "bg-brand-600 font-semibold text-white shadow-sm"
                : "text-slate-600 hover:bg-slate-100 hover:text-brand-600"
            }`}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
