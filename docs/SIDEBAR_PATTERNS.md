# Production Collapsible Sidebar Patterns for Chat Applications

## Overview
This document captures production-quality sidebar implementations from Vercel's Chatbot and Bolt.new, which follow modern chat UI patterns similar to DeepSeek.

---

## 1. LAYOUT ARCHITECTURE

### Sidebar Structure (Vercel Chatbot)
```
Sidebar (collapsible="icon")
├── SidebarHeader (Logo + Toggle)
│   ├── Logo (clickable, toggles on hover when collapsed)
│   └── SidebarTrigger (visible when expanded)
├── SidebarContent (Main scrollable area)
│   ├── SidebarGroup (New Chat button)
│   └── SidebarHistory (Chat history with date grouping)
└── SidebarFooter (User profile)
```

### Key Dimensions
- **Expanded width**: `16rem` (256px)
- **Collapsed width**: `3rem` (48px)
- **Mobile width**: `18rem` (288px)
- **Transition duration**: `300ms`
- **Easing function**: `cubic-bezier(0.22, 1, 0.36, 1)` (smooth, slightly bouncy)

---

## 2. COLLAPSE ANIMATION PATTERNS

### CSS Transition (Vercel Chatbot)
```css
/* Sidebar container */
transition-[left,right,width] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]

/* Sidebar gap (spacing adjustment) */
transition-[width] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]

/* Individual elements */
transition-colors duration-150
transition-opacity duration-150
```

### Framer Motion Variants (Bolt.new)
```typescript
const menuVariants = {
  closed: {
    opacity: 0,
    visibility: 'hidden',
    left: '-150px',
    transition: {
      duration: 0.2,
      ease: cubicEasingFn,
    },
  },
  open: {
    opacity: 1,
    visibility: 'initial',
    left: 0,
    transition: {
      duration: 0.2,
      ease: cubicEasingFn,
    },
  },
};
```

### State-Based Styling
```typescript
// Use data attributes for state-driven CSS
data-state="expanded" | "collapsed"
data-collapsible="icon" | "offcanvas" | "none"

// Conditional rendering based on state
group-data-[collapsible=icon]:hidden  // Hide when collapsed
group-data-[collapsible=icon]:opacity-0  // Fade out
group-data-[collapsible=icon]:pointer-events-none  // Disable interaction
```

---

## 3. LOGO CLICK TOGGLE PATTERN

### Implementation (Vercel Chatbot)
```typescript
<div className="group/logo relative flex items-center justify-center">
  {/* Logo - visible when expanded */}
  <SidebarMenuButton
    asChild
    className="size-8 !px-0 items-center justify-center 
               group-data-[collapsible=icon]:group-hover/logo:opacity-0"
    tooltip="Chatbot"
  >
    <Link href="/" onClick={() => setOpenMobile(false)}>
      <MessageSquareIcon className="size-4 text-sidebar-foreground/50" />
    </Link>
  </SidebarMenuButton>

  {/* Toggle button - appears on hover when collapsed */}
  <Tooltip>
    <TooltipTrigger asChild>
      <SidebarMenuButton
        className="pointer-events-none absolute inset-0 size-8 
                   opacity-0 
                   group-data-[collapsible=icon]:pointer-events-auto 
                   group-data-[collapsible=icon]:group-hover/logo:opacity-100"
        onClick={() => toggleSidebar()}
      >
        <PanelLeftIcon className="size-4" />
      </SidebarMenuButton>
    </TooltipTrigger>
    <TooltipContent className="hidden md:block" side="right">
      Open sidebar
    </TooltipContent>
  </Tooltip>
</div>
```

**Key Pattern**: 
- Logo is always clickable (navigates home)
- Toggle button overlays logo on hover when collapsed
- Uses `pointer-events-none` to prevent interaction when hidden
- Smooth opacity transition on hover

---

## 4. CHAT HISTORY LIST PATTERN

### Date-Based Grouping (Vercel Chatbot)
```typescript
type GroupedChats = {
  today: Chat[];
  yesterday: Chat[];
  lastWeek: Chat[];
  lastMonth: Chat[];
  older: Chat[];
};

// Group chats by date
const groupChatsByDate = (chats: Chat[]): GroupedChats => {
  const now = new Date();
  const oneWeekAgo = subWeeks(now, 1);
  const oneMonthAgo = subMonths(now, 1);

  return chats.reduce((groups, chat) => {
    const chatDate = new Date(chat.createdAt);
    if (isToday(chatDate)) groups.today.push(chat);
    else if (isYesterday(chatDate)) groups.yesterday.push(chat);
    else if (chatDate > oneWeekAgo) groups.lastWeek.push(chat);
    else if (chatDate > oneMonthAgo) groups.lastMonth.push(chat);
    else groups.older.push(chat);
    return groups;
  }, {...});
};
```

### Rendering Structure
```typescript
<SidebarGroup className="group-data-[collapsible=icon]:hidden">
  <SidebarGroupLabel className="text-[10px] font-semibold uppercase 
                               tracking-[0.12em] text-sidebar-foreground/70">
    History
  </SidebarGroupLabel>
  <SidebarGroupContent>
    <SidebarMenu>
      {/* For each date group */}
      <div>
        <div className="px-2 py-1 text-[10px] font-semibold uppercase 
                        tracking-[0.12em] text-sidebar-foreground/70">
          Today
        </div>
        {groupedChats.today.map((chat) => (
          <ChatItem
            chat={chat}
            isActive={chat.id === currentId}
            onDelete={(chatId) => setDeleteId(chatId)}
            setOpenMobile={setOpenMobile}
          />
        ))}
      </div>
    </SidebarMenu>
  </SidebarGroupContent>
</SidebarGroup>
```

### Infinite Scroll Pattern
```typescript
// Use Framer Motion's onViewportEnter for lazy loading
<motion.div
  onViewportEnter={() => {
    if (!isValidating && !hasReachedEnd) {
      setSize((size) => size + 1);  // Load next page
    }
  }}
/>
```

---

## 5. NEW CONVERSATION BUTTON

### Styling Pattern
```typescript
<SidebarMenuButton
  className="h-8 rounded-lg border border-sidebar-border 
             text-[13px] text-sidebar-foreground/70 
             transition-colors duration-150 
             hover:bg-sidebar-accent/50 
             hover:text-sidebar-foreground"
  onClick={() => {
    setOpenMobile(false);
    router.push("/");
  }}
  tooltip="New Chat"
>
  <PenSquareIcon className="size-4" />
  <span className="font-medium">New chat</span>
</SidebarMenuButton>
```

**Key Features**:
- Subtle border (not filled)
- Hover state changes background to accent color
- Icon + text label
- Closes mobile sidebar on click
- Navigates to home route

---

## 6. USER PROFILE AT BOTTOM

### Footer Structure
```typescript
<SidebarFooter className="border-t border-sidebar-border pt-2 pb-3">
  {user && <SidebarUserNav user={user} />}
</SidebarFooter>
```

### Typical User Nav Component
```typescript
// Usually contains:
// - User avatar
// - User name
// - Sign out button
// - Settings link
// All hidden when sidebar is collapsed (via group-data-[collapsible=icon]:hidden)
```

---

## 7. RESPONSIVE BEHAVIOR

### Mobile Handling (Vercel Chatbot)
```typescript
// On mobile, sidebar becomes a bottom sheet
if (isMobile) {
  return (
    <Sheet open={openMobile} onOpenChange={setOpenMobile}>
      <SheetContent
        side="bottom"
        className="inset-x-0 bottom-0 top-auto h-[70dvh] 
                   w-full rounded-t-2xl border-t border-border/30"
      >
        {/* Sidebar content */}
      </SheetContent>
    </Sheet>
  );
}
```

### Keyboard Shortcut
```typescript
// Cmd/Ctrl + B toggles sidebar
const handleKeyDown = (event: KeyboardEvent) => {
  if (
    event.key === 'b' &&
    (event.metaKey || event.ctrlKey)
  ) {
    event.preventDefault();
    toggleSidebar();
  }
};
```

---

## 8. CONTEXT & STATE MANAGEMENT

### Sidebar Context (Vercel Chatbot)
```typescript
type SidebarContextProps = {
  state: "expanded" | "collapsed"
  open: boolean
  setOpen: (open: boolean) => void
  openMobile: boolean
  setOpenMobile: (open: boolean) => void
  isMobile: boolean
  toggleSidebar: () => void
}

// Persist state to cookie
document.cookie = `sidebar_state=${openState}; 
                   path=/; 
                   max-age=${60 * 60 * 24 * 7}`
```

### Hook Usage
```typescript
const { setOpenMobile, toggleSidebar, state } = useSidebar();
```

---

## 9. SKELETON LOADING STATE

### Pattern
```typescript
if (isLoading) {
  return (
    <SidebarGroup className="group-data-[collapsible=icon]:hidden">
      <SidebarGroupLabel>History</SidebarGroupLabel>
      <SidebarGroupContent>
        <div className="flex flex-col gap-0.5 px-1">
          {[44, 32, 28, 64, 52].map((width) => (
            <div className="flex h-8 items-center gap-2 rounded-lg px-2">
              <div
                className="h-3 flex-1 animate-pulse rounded-md 
                           bg-sidebar-foreground/[0.06]"
                style={{ width: `${width}%` }}
              />
            </div>
          ))}
        </div>
      </SidebarGroupContent>
    </SidebarGroup>
  );
}
```

---

## 10. HOVER-BASED SIDEBAR (Bolt.new Alternative)

### Mouse-Triggered Expand
```typescript
useEffect(() => {
  const enterThreshold = 40;
  const exitThreshold = 40;

  function onMouseMove(event: MouseEvent) {
    // Open sidebar when mouse near left edge
    if (event.pageX < enterThreshold) {
      setOpen(true);
    }

    // Close when mouse moves away
    if (menuRef.current && 
        event.clientX > menuRef.current.getBoundingClientRect().right + exitThreshold) {
      setOpen(false);
    }
  }

  window.addEventListener('mousemove', onMouseMove);
  return () => window.removeEventListener('mousemove', onMouseMove);
}, []);
```

---

## 11. COMPONENT COMPOSITION RECOMMENDATIONS

### Folder Structure
```
components/
├── chat/
│   ├── app-sidebar.tsx          # Main sidebar wrapper
│   ├── sidebar-history.tsx      # Chat history list
│   ├── sidebar-history-item.tsx # Individual chat item
│   ├── sidebar-user-nav.tsx     # User profile section
│   └── sidebar-toggle.tsx       # Toggle button
└── ui/
    └── sidebar.tsx              # Base sidebar components (Radix-based)
```

### Component Hierarchy
```
<SidebarProvider>
  <AppSidebar>
    <SidebarHeader>
      {/* Logo + Toggle */}
    </SidebarHeader>
    <SidebarContent>
      <SidebarGroup>
        {/* New Chat Button */}
      </SidebarGroup>
      <SidebarHistory>
        {/* Chat history with date grouping */}
      </SidebarHistory>
    </SidebarContent>
    <SidebarFooter>
      {/* User profile */}
    </SidebarFooter>
  </AppSidebar>
  <SidebarInset>
    {/* Main content area */}
  </SidebarInset>
</SidebarProvider>
```

---

## 12. PRODUCTION CONSIDERATIONS

### Performance
- Use `group-data-[collapsible=icon]:hidden` instead of conditional rendering
- Lazy load chat history with infinite scroll
- Memoize grouped chats to prevent recalculation
- Use `motion.div` with `onViewportEnter` for intersection detection

### Accessibility
- Include `aria-label` on toggle buttons
- Use semantic HTML (nav, button, etc.)
- Keyboard shortcut (Cmd/Ctrl + B)
- Tooltip on hover for collapsed state
- Screen reader text for icon-only buttons

### State Persistence
- Save sidebar state to cookie
- Restore on page load
- Respect user preference (mobile vs desktop)

### Animation Timing
- Collapse/expand: 300ms
- Hover effects: 150ms
- Loading states: smooth pulse animation
- Transitions should feel responsive but not jarring

---

## 13. EXAMPLE: MINIMAL IMPLEMENTATION

```typescript
'use client';

import { useState } from 'react';
import { useSidebar } from '@/components/ui/sidebar';

export function AppSidebar() {
  const { toggleSidebar, state } = useSidebar();

  return (
    <aside className={cn(
      'fixed left-0 top-0 h-full bg-sidebar transition-[width] duration-300',
      state === 'expanded' ? 'w-64' : 'w-16'
    )}>
      {/* Header with logo + toggle */}
      <div className="flex items-center justify-between p-4">
        <div className={cn(
          'transition-opacity duration-300',
          state === 'collapsed' && 'opacity-0'
        )}>
          Logo
        </div>
        <button onClick={toggleSidebar}>
          {state === 'expanded' ? '←' : '→'}
        </button>
      </div>

      {/* Content - hidden when collapsed */}
      <div className={cn(
        'transition-opacity duration-300',
        state === 'collapsed' && 'opacity-0 pointer-events-none'
      )}>
        {/* Chat history, user profile, etc. */}
      </div>
    </aside>
  );
}
```

