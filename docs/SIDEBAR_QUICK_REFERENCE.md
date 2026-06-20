# Collapsible Sidebar - Quick Reference Card

## Dimensions & Timing
```
Expanded Width:     256px (16rem)
Collapsed Width:    48px (3rem)
Mobile Width:       288px (18rem)
Transition Time:    300ms
Hover Effects:      150ms
Easing:             cubic-bezier(0.22, 1, 0.36, 1)
```

## Logo Click Pattern
```typescript
<div className="group/logo relative">
  {/* Logo - always visible */}
  <SidebarMenuButton
    className="group-data-[collapsible=icon]:group-hover/logo:opacity-0"
  >
    <Logo />
  </SidebarMenuButton>

  {/* Toggle - appears on hover when collapsed */}
  <SidebarMenuButton
    className="opacity-0 
               group-data-[collapsible=icon]:pointer-events-auto 
               group-data-[collapsible=icon]:group-hover/logo:opacity-100"
    onClick={() => toggleSidebar()}
  >
    <PanelLeftIcon />
  </SidebarMenuButton>
</div>
```

## Chat History Structure
```
History
├── Today
│   ├── Chat Item 1
│   └── Chat Item 2
├── Yesterday
│   └── Chat Item 3
├── Last 7 days
│   └── Chat Item 4
├── Last 30 days
│   └── Chat Item 5
└── Older
    └── Chat Item 6
```

## Key CSS Classes
```css
/* Sidebar container */
transition-[left,right,width] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]

/* Hide when collapsed */
group-data-[collapsible=icon]:hidden

/* Fade out when collapsed */
group-data-[collapsible=icon]:opacity-0

/* Disable interaction when hidden */
group-data-[collapsible=icon]:pointer-events-none

/* Hover effects */
hover:bg-sidebar-accent/50
hover:text-sidebar-foreground
group-hover:opacity-100

/* Transitions */
transition-colors duration-150
transition-opacity duration-150
```

## State Management
```typescript
// Context
type SidebarContextProps = {
  state: "expanded" | "collapsed"
  open: boolean
  setOpen: (open: boolean) => void
  toggleSidebar: () => void
  isMobile: boolean
  openMobile: boolean
  setOpenMobile: (open: boolean) => void
}

// Hook
const { state, toggleSidebar, setOpenMobile } = useSidebar()

// Persistence
document.cookie = `sidebar_state=${openState}; path=/; max-age=${60*60*24*7}`

// Keyboard Shortcut
Cmd/Ctrl + B to toggle
```

## Component Hierarchy
```
SidebarProvider
  └── AppSidebar
      ├── SidebarHeader
      │   └── Logo + Toggle
      ├── SidebarContent
      │   ├── New Chat Button
      │   └── SidebarHistory
      │       └── SidebarHistoryItem (×N)
      └── SidebarFooter
          └── User Profile
```

## Mobile Behavior
```typescript
// Automatically becomes bottom sheet on mobile
if (isMobile) {
  return (
    <Sheet open={openMobile} onOpenChange={setOpenMobile}>
      <SheetContent
        side="bottom"
        className="h-[70dvh] rounded-t-2xl"
      >
        {/* Sidebar content */}
      </SheetContent>
    </Sheet>
  );
}
```

## Loading State
```typescript
{[44, 32, 28, 64, 52].map((width) => (
  <div className="flex h-8 items-center gap-2 rounded-lg px-2">
    <div
      className="h-3 flex-1 animate-pulse rounded-md 
                 bg-sidebar-foreground/[0.06]"
      style={{ width: `${width}%` }}
    />
  </div>
))}
```

## Infinite Scroll
```typescript
<motion.div
  onViewportEnter={() => {
    if (!isValidating && !hasReachedEnd) {
      setSize((size) => size + 1);
    }
  }}
/>
```

## New Chat Button
```typescript
<SidebarMenuButton
  className="h-8 rounded-lg border border-sidebar-border 
             text-[13px] text-sidebar-foreground/70 
             transition-colors duration-150 
             hover:bg-sidebar-accent/50 
             hover:text-sidebar-foreground"
  onClick={() => {
    setOpenMobile(false);
    router.push("/chat");
  }}
>
  <PenSquareIcon className="size-4" />
  <span className="font-medium">New chat</span>
</SidebarMenuButton>
```

## Accessibility Checklist
- ✅ Keyboard shortcut (Cmd/Ctrl + B)
- ✅ Tooltips on icon-only buttons
- ✅ Semantic HTML (nav, button, etc.)
- ✅ ARIA labels on interactive elements
- ✅ Screen reader text for icons
- ✅ Focus management
- ✅ Color contrast (WCAG AA)

## Performance Tips
1. Use `group-data-[collapsible=icon]:hidden` instead of conditional rendering
2. Memoize grouped chats with `useMemo`
3. Lazy load with infinite scroll
4. Use SWR for caching
5. Avoid re-rendering entire history on state change

## Dependencies
```bash
npm install @radix-ui/react-dialog @radix-ui/react-slot
npm install framer-motion sonner swr
npm install class-variance-authority clsx tailwind-merge
```

## File Structure
```
components/
├── chat/
│   ├── AppSidebar.tsx
│   ├── SidebarHistory.tsx
│   ├── SidebarHistoryItem.tsx
│   └── SidebarFooter.tsx
└── ui/
    └── sidebar.tsx
```

## Implementation Order
1. Create base sidebar.tsx (Radix UI)
2. Create AppSidebar wrapper
3. Create SidebarHistory component
4. Create SidebarHistoryItem component
5. Connect to backend API
6. Add infinite scroll
7. Test on mobile
8. Optimize performance

## Common Pitfalls
❌ Using conditional rendering instead of data attributes
❌ Forgetting `pointer-events-none` on hidden elements
❌ Not memoizing grouped chats
❌ Missing keyboard shortcut
❌ Not testing on mobile
❌ Forgetting accessibility labels
❌ Using wrong easing function

## References
- Vercel Chatbot: https://github.com/vercel/chatbot
- Bolt.new: https://github.com/stackblitz/bolt.new
- Radix UI: https://www.radix-ui.com/
- Tailwind CSS: https://tailwindcss.com/

