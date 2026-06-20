# Collapsible Sidebar Pattern Summary

## What You've Learned

You now have concrete, production-tested patterns for implementing a collapsible sidebar similar to DeepSeek's chat interface. This research is based on:

1. **Vercel Chatbot** (https://github.com/vercel/chatbot) - Full-featured chat with user accounts
2. **Bolt.new** (https://github.com/stackblitz/bolt.new) - Lightweight chat with hover-triggered sidebar
3. **DeepSeek V4 Design Guide** - Modern AI chat UI principles

---

## Key Patterns Discovered

### 1. Layout & Dimensions
- **Expanded**: 256px (16rem)
- **Collapsed**: 48px (3rem)
- **Mobile**: 288px (18rem) as bottom sheet
- **Transition**: 300ms with cubic-bezier(0.22, 1, 0.36, 1) easing

### 2. Logo Click Toggle
- Logo always clickable (navigates home)
- Toggle button overlays logo on hover when collapsed
- Uses `pointer-events-none` to prevent interaction when hidden
- Smooth opacity transition

### 3. Chat History
- Date-based grouping: Today, Yesterday, Last 7 days, Last 30 days, Older
- Infinite scroll with Framer Motion's `onViewportEnter`
- Skeleton loading state with animated placeholders
- Active state highlighting for current chat

### 4. New Conversation Button
- Subtle border (not filled)
- Hover state changes background to accent color
- Icon + text label
- Closes mobile sidebar on click

### 5. User Profile (Footer)
- Border separator from content
- Hidden when sidebar collapsed
- Contains avatar, name, sign out, settings

### 6. Animations
- **Collapse/expand**: 300ms
- **Hover effects**: 150ms
- **Loading states**: Smooth pulse animation
- **Easing**: cubic-bezier(0.22, 1, 0.36, 1) for premium feel

### 7. State Management
- React Context + cookies for persistence
- Keyboard shortcut: Cmd/Ctrl + B
- Mobile detection with `useIsMobile()` hook
- Automatic bottom sheet on mobile

### 8. Accessibility
- Semantic HTML (nav, button, etc.)
- ARIA labels on interactive elements
- Tooltips on icon-only buttons
- Screen reader text
- Focus management
- Keyboard navigation

---

## Three Implementation Approaches

### Option A: Radix UI + Tailwind (Recommended)
**Best for**: Full-featured chat with persistence
- Production-tested
- Excellent accessibility
- Smooth CSS transitions
- Cookie-based persistence
- Works with Tailwind

### Option B: Framer Motion
**Best for**: Lightweight chat without persistence
- Simpler component structure
- Powerful animation control
- Hover-triggered sidebar
- Smaller bundle size

### Option C: Pure CSS + React
**Best for**: MVP or simple Q&A
- No external animation library
- Smallest bundle size
- Full control
- More CSS to write

---

## Component Structure

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

## Critical CSS Classes

```css
/* Sidebar container */
transition-[left,right,width] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]

/* State-based visibility */
group-data-[collapsible=icon]:hidden
group-data-[collapsible=icon]:opacity-0
group-data-[collapsible=icon]:pointer-events-none

/* Hover effects */
hover:bg-sidebar-accent/50
hover:text-sidebar-foreground
group-hover:opacity-100

/* Transitions */
transition-colors duration-150
transition-opacity duration-150
```

---

## Production Considerations

### Performance
- Use data attributes instead of conditional rendering
- Lazy load chat history with infinite scroll
- Memoize grouped chats
- Use Framer Motion's `onViewportEnter` for intersection detection

### Accessibility
- Keyboard shortcut (Cmd/Ctrl + B)
- Tooltips on icon-only buttons
- Semantic HTML
- ARIA labels
- Screen reader text

### State Persistence
- Save to cookie
- Restore on page load
- Respect user preference (mobile vs desktop)

### Animation Timing
- Collapse/expand: 300ms
- Hover effects: 150ms
- Loading states: smooth pulse
- Transitions should feel responsive but not jarring

---

## For SubSkin Implementation

### Recommended Approach
Use **Option A (Radix UI + Tailwind)** because:
1. You're building a full-featured chat application
2. You'll need user accounts and history persistence
3. Excellent accessibility for medical content
4. Production-tested by Vercel
5. Works with your existing tech stack

### Phase 1 (MVP)
- Basic sidebar with static chat list
- Logo click toggle
- New chat button
- Mobile bottom sheet

### Phase 2 (Production)
- Connect to backend API
- Infinite scroll pagination
- Date-based grouping
- Delete functionality

### Phase 3 (Enhancement)
- User authentication
- Profile section
- Search/filter
- Chat renaming

---

## Files You Have

1. **sidebar-patterns.md** - Complete pattern reference (13 sections)
2. **production-code-reference.md** - Actual code from Vercel Chatbot
3. **implementation-guide.md** - Step-by-step implementation for SubSkin
4. **SUMMARY.md** - This file

---

## Next Actions

1. **Review** the production code reference to understand the patterns
2. **Choose** your implementation approach (Radix UI recommended)
3. **Start** with the base sidebar component
4. **Build** AppSidebar, SidebarHistory, SidebarHistoryItem
5. **Connect** to your backend API
6. **Test** on mobile and desktop
7. **Optimize** performance with infinite scroll

---

## Key Takeaways

✅ **Logo click pattern**: Overlay toggle button on hover when collapsed
✅ **Animation timing**: 300ms for collapse/expand, 150ms for hover
✅ **Easing function**: cubic-bezier(0.22, 1, 0.36, 1) for premium feel
✅ **State management**: React Context + cookies
✅ **Mobile**: Automatic bottom sheet (no extra code needed)
✅ **Accessibility**: Keyboard shortcut, tooltips, semantic HTML
✅ **Performance**: Infinite scroll, memoization, lazy loading
✅ **Chat history**: Date-based grouping (Today, Yesterday, etc.)

---

## References

- **Vercel Chatbot**: https://github.com/vercel/chatbot
- **Bolt.new**: https://github.com/stackblitz/bolt.new
- **DeepSeek V4 Design**: Modern AI chat UI principles
- **Radix UI**: https://www.radix-ui.com/
- **Tailwind CSS**: https://tailwindcss.com/

