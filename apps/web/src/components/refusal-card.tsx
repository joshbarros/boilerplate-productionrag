import { AlertTriangle, XCircle, Info } from "lucide-react";
import { cn } from "@/lib/cn";

type Tone = "warning" | "error" | "info";

const toneStyles: Record<
  Tone,
  { icon: typeof AlertTriangle; color: string; bg: string }
> = {
  warning: {
    icon: AlertTriangle,
    color: "text-warning",
    bg: "border-warning/30 bg-warning/5",
  },
  error: {
    icon: XCircle,
    color: "text-error",
    bg: "border-error/30 bg-error/5",
  },
  info: { icon: Info, color: "text-info", bg: "border-info/30 bg-info/5" },
};

export function RefusalCard({
  reason,
  detail,
  tone = "info",
}: {
  reason: string;
  detail?: string;
  tone?: Tone;
}) {
  const s = toneStyles[tone];
  const Icon = s.icon;
  return (
    <div className={cn("hairline rounded-md border px-4 py-3", s.bg)}>
      <div className="flex items-start gap-3">
        <Icon
          className={cn("mt-0.5 h-4 w-4 shrink-0", s.color)}
          strokeWidth={1.5}
        />
        <div className="space-y-0.5">
          <p className="text-sm font-medium text-text">{reason}</p>
          {detail && <p className="text-xs text-text-muted">{detail}</p>}
        </div>
      </div>
    </div>
  );
}
