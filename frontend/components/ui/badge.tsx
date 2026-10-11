import * as React from "react";
import { cn } from "@/lib/utils";

export function Badge({ className, ...p }: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-muted text-muted-foreground",
        className
      )}
      {...p}
    />
  );
}
