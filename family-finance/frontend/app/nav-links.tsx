"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/net-worth", label: "Net Worth" },
  { href: "/transactions", label: "Transactions" },
  { href: "/categories", label: "Categories" },
  { href: "/statement-log", label: "Statement Log" },
];

export default function NavLinks() {
  const pathname = usePathname();
  return (
    <nav className="flex flex-wrap items-center gap-4 text-sm font-medium">
      {LINKS.map((link) => {
        const active = pathname === link.href;
        return (
          <Link
            key={link.href}
            href={link.href}
            aria-current={active ? "page" : undefined}
            className={active ? "text-brand-700" : "text-slate-600 hover:text-brand-600"}
          >
            {link.label}
          </Link>
        );
      })}
      <Link
        href="/upload"
        aria-current={pathname === "/upload" ? "page" : undefined}
        className={`rounded-md px-3 py-1.5 font-medium text-white shadow-sm ${
          pathname === "/upload"
            ? "bg-brand-700"
            : "bg-brand-500 hover:bg-brand-600"
        }`}
      >
        + Upload Statement
      </Link>
    </nav>
  );
}
