"use client"

import { Popover as PopoverPrimitive } from "@base-ui/react/popover"
import { cn } from "cn"

function Popover(props: PopoverPrimitive.Root.Props) {
  return <PopoverPrimitive.Root {...props} />
}

function PopoverTrigger({ className, ...props }: PopoverPrimitive.Trigger.Props) {
  return (
    <PopoverPrimitive.Trigger data-slot="popover-trigger" className={className} {...props} />
  )
}

function PopoverContent({
  className,
  side = "top",
  align = "start",
  sideOffset = 6,
  ...props
}: PopoverPrimitive.Popup.Props &
  Pick<PopoverPrimitive.Positioner.Props, "side" | "align" | "sideOffset">) {
  return (
    <PopoverPrimitive.Portal>
      {/* The z-index belongs on the positioner: it is the positioned element,
          and a z-index on the statically laid-out popup does nothing, which
          left the popup rendering *behind* the message it belongs to. */}
      <PopoverPrimitive.Positioner
        className="z-50"
        side={side}
        align={align}
        sideOffset={sideOffset}
      >
        <PopoverPrimitive.Popup
          data-slot="popover-content"
          className={cn(
            "max-h-[min(24rem,var(--available-height))] w-72 max-w-[calc(100vw-2rem)] origin-[var(--transform-origin)] overflow-y-auto rounded-lg border bg-popover p-3 text-popover-foreground shadow-lg outline-none",
            "transition-[transform,scale,opacity] data-ending-style:scale-95 data-ending-style:opacity-0 data-starting-style:scale-95 data-starting-style:opacity-0",
            className
          )}
          {...props}
        />
      </PopoverPrimitive.Positioner>
    </PopoverPrimitive.Portal>
  )
}

export { Popover, PopoverTrigger, PopoverContent }
