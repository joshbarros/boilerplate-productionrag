"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { MessageSquare, FileUp, Gauge } from "lucide-react";
import { cn } from "@/lib/cn";

const navItems = [
  { href: "/", label: "Chat", icon: MessageSquare },
  { href: "/ingest", label: "Documents", icon: FileUp },
  { href: "/budget", label: "Budget", icon: Gauge },
];

export function TopNav() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-bg/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-[1200px] items-center gap-8 px-6">
        <Link href="/" className="flex items-center gap-2">
          <span className="accent-gradient h-5 w-5 rounded-sm" />
          <span className="font-semibold tracking-tight">production-rag</span>
        </Link>
        <nav className="flex items-center gap-1">
          {navItems.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition-colors",
                  isActive
                    ? "text-text"
                    : "text-text-muted hover:bg-surface hover:text-text",
                )}
              >
                <item.icon className="h-3.5 w-3.5" strokeWidth={1.5} />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <BudgetPill />
        </div>
      </div>
    </header>
  );
}

function BudgetPill() {
  // Lightweight read from the budget API; failures are silent (nav never breaks)
  return (
    <div className="flex items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 py-1 text-xs">
      <span className="h-1.5 w-1.5 rounded-full bg-success pulse-dot" />
      <span className="mono-num text-text-muted">$0.00</span>
      <span className="text-text-faint">/</span>
      <span className="mono-num text-text-faint">$5.00</span>
    </div>
  );
}
