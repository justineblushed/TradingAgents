"use client";

import Link from "next/link";

/** Shown wherever a page's income figure could be dragged wrong by a
 *  mis-signed transaction — shows only when the number on screen actually
 *  looks broken (negative income), not as a standing nag on every visit. */
export default function SignIssueBanner() {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
      <span>
        ⚠ Income showing as a negative number usually means one or more
        transactions were stored with the wrong sign.
      </span>
      <Link
        href="/sign-check"
        className="shrink-0 font-medium text-amber-900 underline hover:text-amber-700"
      >
        Review and fix
      </Link>
    </div>
  );
}
