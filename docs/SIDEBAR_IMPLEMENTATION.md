# Implementation Guide: Collapsible Sidebar for SubSkin Chat

## Quick Start Recommendations

Based on production patterns from Vercel Chatbot and Bolt.new, here's how to implement for your Q&A/chat page.

---

## 1. CHOOSE YOUR APPROACH

### Option A: Radix UI + Tailwind (Recommended for SubSkin)
**Pros:**
- Production-tested (Vercel uses this)
- Excellent accessibility
- Smooth animations with CSS transitions
- Works with existing Tailwind setup
- Cookie-based state persistence

**Cons:**
- Requires Radix UI library
- More boilerplate initially

**Best for:** Full-featured chat with user accounts, history persistence

### Option B: Framer Motion (Bolt.new Style)
**Pros:**
- Simpler component structure
- Powerful animation control
- Great for hover-triggered sidebars
- Smaller bundle size

**Cons:**
- Requires Framer Motion dependency
- Less built-in accessibility features
- Manual state management

**Best for:** Lightweight chat without persistence requirements

### Option C: Pure CSS + React (Minimal)
**Pros:**
- No external animation library
- Smallest bundle size
- Full control

**Cons:**
- More CSS to write
- Less sophisticated animations
- Manual accessibility handling

**Best for:** MVP or simple Q&A interface

---

## 2. RECOMMENDED ARCHITECTURE FOR SUBSKIN

Given SubSkin's tech stack (Python backend, planned VitePress frontend), I recommend **Option A** with this structure:

```
src/components/
├── chat/
│   ├── ChatPage.tsx              # Main page component
│   ├── AppSidebar.tsx            # Sidebar wrapper
│   ├── SidebarHeader.tsx         # Logo + toggle
│   ├── SidebarHistory.tsx        # Chat history list
│   ├── SidebarHistoryItem.tsx    # Individual chat item
│   ├── SidebarFooter.tsx         # User profile (future)
│   └── ChatContent.tsx           # Main chat area
└── ui/
    └── sidebar.tsx               # Base Radix components
```

---

## 3. IMPLEMENTATION STEPS

### Step 1: Install Dependencies
```bash
npm install @radix-ui/react-dialog @radix-ui/react-slot
npm install framer-motion sonner swr
npm install class-variance-authority clsx tailwind-merge
```

### Step 2: Create Base Sidebar Component (ui/sidebar.tsx)

Use the Vercel Chatbot sidebar.tsx as your base. Key features:
- `SidebarProvider` context for state management
- `useSidebar()` hook for accessing state
- Cookie persistence
- Keyboard shortcut (Cmd/Ctrl + B)
- Mobile responsive (bottom sheet on mobile)

### Step 3: Create AppSidebar Component

```typescript
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { MessageSquareIcon, PenSquareIcon, PanelLeftIcon } from 'lucide-react';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  SidebarTrigger,
  useSidebar,
} from '@/components/ui/sidebar';
import { SidebarHistory } from './SidebarHistory';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

export function AppSidebar() {
  const router = useRouter();
  const { setOpenMobile, toggleSidebar } = useSidebar();

  return (
    <Sidebar collapsible="icon">
      {/* Header: Logo + Toggle */}
      <SidebarHeader className="pb-0 pt-3">
        <SidebarMenu>
          <SidebarMenuItem className="flex flex-row items-center justify-between">
            <div className="group/logo relative flex items-center justify-center">
              {/* Logo - navigates to home */}
              <SidebarMenuButton
                asChild
                className="size-8 !px-0 items-center justify-center 
                           group-data-[collapsible=icon]:group-hover/logo:opacity-0"
                tooltip="SubSkin"
              >
                <a href="/" onClick={() => setOpenMobile(false)}>
                  <MessageSquareIcon className="size-4 text-sidebar-foreground/50" />
                </a>
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

            {/* Trigger button - visible when expanded */}
            <div className="group-data-[collapsible=icon]:hidden">
              <SidebarTrigger className="text-sidebar-foreground/60 
                                        transition-colors duration-150 
                                        hover:text-sidebar-foreground" />
            </div>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      {/* Content: New Chat + History */}
      <SidebarContent>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              className="h-8 rounded-lg border border-sidebar-border 
                         text-[13px] text-sidebar-foreground/70 
                         transition-colors duration-150 
                         hover:bg-sidebar-accent/50 
                         hover:text-sidebar-foreground"
              onClick={() => {
                setOpenMobile(false);
                router.push('/chat');
              }}
              tooltip="New Chat"
            >
              <PenSquareIcon className="size-4" />
              <span className="font-medium">New chat</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>

        {/* Chat history component */}
        <SidebarHistory />
      </SidebarContent>

      {/* Footer: User profile (future) */}
      <SidebarFooter className="border-t border-sidebar-border pt-2 pb-3">
        {/* User profile will go here */}
      </SidebarFooter>

      <SidebarRail />
    </Sidebar>
  );
}
```

### Step 4: Create SidebarHistory Component

```typescript
'use client';

import { useState, useMemo } from 'react';
import { usePathname } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  useSidebar,
} from '@/components/ui/sidebar';
import { SidebarHistoryItem } from './SidebarHistoryItem';

interface Chat {
  id: string;
  title: string;
  createdAt: Date;
}

export function SidebarHistory() {
  const { setOpenMobile } = useSidebar();
  const pathname = usePathname();
  const currentChatId = pathname?.startsWith('/chat/') 
    ? pathname.split('/')[2] 
    : null;

  // TODO: Replace with actual API call to fetch chats
  const [chats, setChats] = useState<Chat[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Group chats by date
  const groupedChats = useMemo(() => {
    const now = new Date();
    const today = chats.filter(chat => {
      const chatDate = new Date(chat.createdAt);
      return chatDate.toDateString() === now.toDateString();
    });

    const yesterday = chats.filter(chat => {
      const chatDate = new Date(chat.createdAt);
      const yesterdayDate = new Date(now);
      yesterdayDate.setDate(yesterdayDate.getDate() - 1);
      return chatDate.toDateString() === yesterdayDate.toDateString();
    });

    const older = chats.filter(chat => !today.includes(chat) && !yesterday.includes(chat));

    return { today, yesterday, older };
  }, [chats]);

  if (isLoading) {
    return (
      <SidebarGroup className="group-data-[collapsible=icon]:hidden">
        <SidebarGroupLabel>History</SidebarGroupLabel>
        <SidebarGroupContent>
          <div className="flex flex-col gap-0.5 px-1">
            {[44, 32, 28].map((width) => (
              <div key={width} className="flex h-8 items-center gap-2 rounded-lg px-2">
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

  if (chats.length === 0) {
    return (
      <SidebarGroup className="group-data-[collapsible=icon]:hidden">
        <SidebarGroupLabel>History</SidebarGroupLabel>
        <SidebarGroupContent>
          <div className="text-[13px] text-sidebar-foreground/60 px-2">
            No conversations yet. Start a new chat!
          </div>
        </SidebarGroupContent>
      </SidebarGroup>
    );
  }

  return (
    <SidebarGroup className="group-data-[collapsible=icon]:hidden">
      <SidebarGroupLabel className="text-[10px] font-semibold uppercase 
                                   tracking-[0.12em] text-sidebar-foreground/70">
        History
      </SidebarGroupLabel>
      <SidebarGroupContent>
        <SidebarMenu>
          <div className="flex flex-col gap-4">
            {groupedChats.today.length > 0 && (
              <div>
                <div className="px-2 py-1 text-[10px] font-semibold uppercase 
                               tracking-[0.12em] text-sidebar-foreground/70">
                  Today
                </div>
                {groupedChats.today.map((chat) => (
                  <SidebarHistoryItem
                    key={chat.id}
                    chat={chat}
                    isActive={chat.id === currentChatId}
                    onSelect={() => setOpenMobile(false)}
                  />
                ))}
              </div>
            )}

            {groupedChats.yesterday.length > 0 && (
              <div>
                <div className="px-2 py-1 text-[10px] font-semibold uppercase 
                               tracking-[0.12em] text-sidebar-foreground/70">
                  Yesterday
                </div>
                {groupedChats.yesterday.map((chat) => (
                  <SidebarHistoryItem
                    key={chat.id}
                    chat={chat}
                    isActive={chat.id === currentChatId}
                    onSelect={() => setOpenMobile(false)}
                  />
                ))}
              </div>
            )}

            {groupedChats.older.length > 0 && (
              <div>
                <div className="px-2 py-1 text-[10px] font-semibold uppercase 
                               tracking-[0.12em] text-sidebar-foreground/70">
                  Older
                </div>
                {groupedChats.older.map((chat) => (
                  <SidebarHistoryItem
                    key={chat.id}
                    chat={chat}
                    isActive={chat.id === currentChatId}
                    onSelect={() => setOpenMobile(false)}
                  />
                ))}
              </div>
            )}
          </div>
        </SidebarMenu>

        {/* Infinite scroll trigger */}
        <motion.div
          onViewportEnter={() => {
            // TODO: Load more chats
          }}
        />
      </SidebarGroupContent>
    </SidebarGroup>
  );
}
```

### Step 5: Create SidebarHistoryItem Component

```typescript
'use client';

import { useRouter } from 'next/navigation';
import { Trash2Icon } from 'lucide-react';
import { SidebarMenuButton, SidebarMenuItem } from '@/components/ui/sidebar';

interface Chat {
  id: string;
  title: string;
  createdAt: Date;
}

interface SidebarHistoryItemProps {
  chat: Chat;
  isActive: boolean;
  onSelect: () => void;
  onDelete?: (chatId: string) => void;
}

export function SidebarHistoryItem({
  chat,
  isActive,
  onSelect,
  onDelete,
}: SidebarHistoryItemProps) {
  const router = useRouter();

  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        asChild
        isActive={isActive}
        className="text-[13px] text-sidebar-foreground/70 
                   hover:text-sidebar-foreground 
                   hover:bg-sidebar-accent/50
                   transition-colors duration-150"
        onClick={() => {
          onSelect();
          router.push(`/chat/${chat.id}`);
        }}
      >
        <a href={`/chat/${chat.id}`} className="flex-1 truncate">
          {chat.title}
        </a>
      </SidebarMenuButton>

      {/* Delete button on hover */}
      {onDelete && (
        <button
          onClick={(e) => {
            e.preventDefault();
            onDelete(chat.id);
          }}
          className="opacity-0 group-hover:opacity-100 transition-opacity 
                     p-1 hover:text-destructive"
          aria-label="Delete chat"
        >
          <Trash2Icon className="size-4" />
        </button>
      )}
    </SidebarMenuItem>
  );
}
```

---

## 4. CSS ANIMATION REFERENCE

### Key Tailwind Classes to Use

```css
/* Sidebar container */
transition-[left,right,width] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]

/* Individual elements */
transition-colors duration-150
transition-opacity duration-150
group-data-[collapsible=icon]:hidden
group-data-[collapsible=icon]:opacity-0
group-data-[collapsible=icon]:pointer-events-none

/* Hover effects */
hover:bg-sidebar-accent/50
hover:text-sidebar-foreground
group-hover:opacity-100
```

### Custom CSS (if needed)

```css
@layer components {
  .sidebar-transition {
    @apply transition-[width,left,right] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)];
  }

  .sidebar-item-hover {
    @apply hover:bg-sidebar-accent/50 hover:text-sidebar-foreground transition-colors duration-150;
  }
}
```

---

## 5. STATE MANAGEMENT FLOW

```
SidebarProvider (Context)
  ├── state: "expanded" | "collapsed"
  ├── open: boolean
  ├── setOpen: (open: boolean) => void
  ├── toggleSidebar: () => void
  └── Persists to cookie: sidebar_state

AppSidebar
  ├── Uses useSidebar() hook
  ├── Calls toggleSidebar() on logo hover
  └── Passes setOpenMobile to children

SidebarHistory
  ├── Fetches chats from API
  ├── Groups by date
  └── Renders SidebarHistoryItem

SidebarHistoryItem
  ├── Navigates to /chat/{id} on click
  └── Shows delete button on hover
```

---

## 6. INTEGRATION WITH SUBSKIN BACKEND

### API Endpoints Needed

```typescript
// GET /api/chats - Fetch user's chat history
interface ChatHistoryResponse {
  chats: Array<{
    id: string;
    title: string;
    createdAt: string;
    updatedAt: string;
  }>;
  hasMore: boolean;
}

// POST /api/chats - Create new chat
interface CreateChatRequest {
  title: string;
  initialQuestion?: string;
}

// DELETE /api/chats/{id} - Delete chat
// PUT /api/chats/{id} - Update chat title
```

### Fetch Implementation

```typescript
// hooks/useChats.ts
import useSWRInfinite from 'swr/infinite';

const PAGE_SIZE = 20;

export function useChats() {
  const { data, setSize, isValidating, isLoading, mutate } = useSWRInfinite(
    (pageIndex) => `/api/chats?page=${pageIndex}&limit=${PAGE_SIZE}`,
    fetch,
    { fallbackData: [] }
  );

  return {
    chats: data?.flatMap(page => page.chats) ?? [],
    isLoading,
    isValidating,
    loadMore: () => setSize(size => size + 1),
    mutate,
  };
}
```

---

## 7. MOBILE RESPONSIVENESS

The sidebar automatically becomes a bottom sheet on mobile (via `useIsMobile()` hook).

**Mobile behavior:**
- Sidebar slides up from bottom
- 70% of viewport height
- Rounded top corners
- Closes when user selects a chat
- Closes when clicking outside

No additional code needed - handled by base Sidebar component!

---

## 8. ACCESSIBILITY CHECKLIST

- ✅ Keyboard shortcut: Cmd/Ctrl + B to toggle
- ✅ Tooltips on icon-only buttons
- ✅ Semantic HTML (nav, button, etc.)
- ✅ ARIA labels on interactive elements
- ✅ Focus management
- ✅ Screen reader text for icon buttons
- ✅ Color contrast meets WCAG AA

---

## 9. PERFORMANCE OPTIMIZATION

```typescript
// Memoize grouped chats
const groupedChats = useMemo(() => {
  // grouping logic
}, [chats]);

// Lazy load with infinite scroll
<motion.div
  onViewportEnter={() => {
    if (!isValidating && hasMore) {
      loadMore();
    }
  }}
/>

// Use SWR for caching
const { data, mutate } = useSWRInfinite(key, fetcher, {
  revalidateOnFocus: false,
  dedupingInterval: 60000,
});
```

---

## 10. NEXT STEPS FOR SUBSKIN

1. **Phase 1**: Implement basic sidebar with static chat list
2. **Phase 2**: Connect to backend API for dynamic chat history
3. **Phase 3**: Add user authentication and profile section
4. **Phase 4**: Implement infinite scroll and pagination
5. **Phase 5**: Add search/filter for chat history

---

## References

- **Vercel Chatbot**: https://github.com/vercel/chatbot/blob/main/components/chat/app-sidebar.tsx
- **Bolt.new**: https://github.com/stackblitz/bolt.new/blob/main/app/components/sidebar/Menu.client.tsx
- **Radix UI Sidebar**: https://github.com/shadcn-ui/ui/blob/main/apps/www/components/ui/sidebar.tsx

