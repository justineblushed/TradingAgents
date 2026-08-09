"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/transactions", label: "Transactions" },
  { href: "/upload", label: "Upload Statement" },
];

export default function NavLinks() {
  const pathname = usePathname();
  return (
    <nav className="flex gap-4 text-sm font-medium">
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
    </nav>
  );
}
