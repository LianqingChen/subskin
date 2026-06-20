# Editor Selection Decision for SubSkin Community Module

## Quick Decision Matrix

### For Your Vitiligo Community Platform: **Use Memos Architecture**

| Criterion | Winner | Why |
|-----------|--------|-----|
| **Mobile Performance** | Memos | Lightweight textarea, no heavy JS framework overhead |
| **Audio Journaling** | Memos | Built-in `useAudioRecorder` + transcription support |
| **Quick Capture UX** | Memos | "Open, write, done" - minimal friction |
| **Privacy** | Memos | Self-hosted, no telemetry, data stays on device |
| **File Uploads** | Memos | Drag-drop + `useFileUpload` hook pattern |
| **Health Metadata** | Custom | Add severity, treatment, mood fields (not in Memos) |
| **Collaboration** | Outline | If you need doctor comments (add later) |

---

## Architecture Decision

### Core Editor: Textarea + Markdown (Memos Pattern)

**Why NOT ProseMirror (Outline)?**
- ❌ 200KB+ bundle size (slow on mobile)
- ❌ Overkill for health journaling
- ❌ Requires backend server
- ❌ Complex plugin system

**Why NOT Block Editor (SiYuan)?**
- ❌ Steep learning curve for patients
- ❌ Requires Electron/native app
- ❌ Too many features (database views, flashcards, etc.)
- ❌ Complex transaction system

**Why Textarea + Markdown?**
- ✅ ~5KB minified (vs 200KB for ProseMirror)
- ✅ Works offline
- ✅ Portable (markdown is future-proof)
- ✅ Simple to understand
- ✅ Proven by Memos (58K GitHub stars)

---

## Implementation Roadmap

### Phase 1: MVP (Weeks 1-2)
```
┌─────────────────────────────────────┐
│  Health Journal Entry               │
├─────────────────────────────────────┤
│  [Textarea - Markdown editor]       │
│                                     │
│  # How I'm feeling today            │
│  Itching on face, applied steroid   │
│                                     │
├─────────────────────────────────────┤
│ Metadata Sidebar:                   │
│ • Severity: [0-10 slider]           │
│ • Treatment: [text input]           │
│ • Mood: [0-10 slider]               │
│ • Location: [text input]            │
│ • Photos: [upload area]             │
└─────────────────────────────────────┘
```

**Components to build:**
1. `MemoEditor` - Textarea wrapper with auto-save
2. `HealthMetadataEditor` - Severity, treatment, mood, location
3. `ImageUploader` - Drag-drop image upload with preview
4. `JournalTimeline` - List of past entries

**Code to reuse from Memos:**
- `useFileUpload` hook
- `useDragAndDrop` hook
- `useBlobUrls` hook
- `AttachmentListEditor` component

### Phase 2: Rich Media (Weeks 3-4)
```
┌─────────────────────────────────────┐
│  [Textarea]                         │
│  [Audio Recorder Button]            │
│  [Image Upload Button]              │
│  [File Upload Button]               │
├─────────────────────────────────────┤
│ Attachments:                        │
│ 🎤 voice-note.webm (2:34)          │
│ 📷 before.jpg (1.2 MB)             │
│ 📷 after.jpg (1.1 MB)              │
│ 📄 prescription.pdf (340 KB)        │
└─────────────────────────────────────┘
```

**Add:**
- `useAudioRecorder` hook (from Memos)
- `AudioRecorderPanel` component
- `useAudioWaveform` for live visualization
- AI transcription integration (OpenAI Whisper API)

### Phase 3: Community Features (Weeks 5-6)
```
┌─────────────────────────────────────┐
│  Journal Entry                      │
│  [Textarea]                         │
│  [Attachments]                      │
├─────────────────────────────────────┤
│ Comments from community:            │
│ 👨‍⚕️ Dr. Chen: "Try phototherapy"    │
│ 👩‍🤝‍👨 Support group: "Same here!"    │
│ [Add comment button]                │
└─────────────────────────────────────┘
```

**Add:**
- Comments system (from Outline pattern)
- Floating toolbar for formatting
- Share with support group
- Doctor feedback

---

## Code Patterns to Adopt

### 1. File Upload (Memos)
```typescript
// hooks/useFileUpload.ts
export const useFileUpload = (onFilesSelected: (files: LocalFile[]) => void) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const handleFileInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    const localFiles: LocalFile[] = files.map((file) => ({
      file,
      previewUrl: URL.createObjectURL(file),
      origin: "upload",
    }));
    onFilesSelected(localFiles);
  };
  
  return { fileInputRef, handleFileInputChange, handleUploadClick };
};
```

### 2. Drag & Drop (Memos)
```typescript
// hooks/useDragAndDrop.ts
export function useDragAndDrop(onDrop: (files: FileList) => void) {
  return {
    dragHandlers: {
      onDragOver: (e: React.DragEvent) => {
        if (e.dataTransfer?.types.includes("Files")) {
          e.preventDefault();
          e.dataTransfer.dropEffect = "copy";
        }
      },
      onDrop: (e: React.DragEvent) => {
        e.preventDefault();
        onDrop(e.dataTransfer?.files);
      },
    },
  };
}
```

### 3. Audio Recording (Memos)
```typescript
// hooks/useAudioRecorder.ts
export const useAudioRecorder = () => {
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const [status, setStatus] = useState<"idle" | "recording">("idle");
  
  const startRecording = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.start();
    setStatus("recording");
  };
  
  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    setStatus("idle");
  };
  
  return { startRecording, stopRecording, status };
};
```

### 4. Mobile Responsiveness (Memos)
```typescript
// Use Tailwind CSS for responsive design
<div className="flex flex-col md:flex-row gap-4">
  {/* Editor takes full width on mobile, 2/3 on desktop */}
  <div className="w-full md:w-2/3">
    <textarea className="w-full h-96" />
  </div>
  
  {/* Metadata sidebar collapses on mobile */}
  <div className="w-full md:w-1/3">
    <HealthMetadataEditor />
  </div>
</div>
```

---

## Tech Stack

```
Frontend:
├── React 18 + TypeScript
├── Vite (bundler)
├── Tailwind CSS v4 (responsive design)
├── React Query v5 (data fetching)
└── Zustand (state management)

Editor:
├── Textarea (plain HTML)
├── Markdown parser (marked or remark)
└── Custom components for health metadata

Media:
├── MediaRecorder API (audio)
├── File API (uploads)
├── Blob URLs (previews)
└── S3/Cloudflare R2 (storage)

Backend:
├── Go (Echo v5) or Node.js (Express)
├── SQLite (local) or PostgreSQL (production)
├── gRPC + Connect RPC (API)
└── OpenAI Whisper (audio transcription)

Mobile:
├── Web-responsive design (Tailwind)
├── Touch-friendly UI
└── Native audio recording (MediaRecorder)
```

---

## Files to Reference

1. **Memos MemoEditor**: https://github.com/usememos/memos/blob/main/web/src/components/MemoEditor/
   - `index.tsx` - Main editor component
   - `Editor/index.tsx` - Textarea wrapper
   - `hooks/useFileUpload.ts` - File upload pattern
   - `hooks/useDragAndDrop.ts` - Drag-drop pattern
   - `hooks/useAudioRecorder.ts` - Audio recording

2. **Memos Attachment Handling**: https://github.com/usememos/memos/blob/main/web/src/components/MemoMetadata/Attachment/
   - `AttachmentListEditor.tsx` - Attachment UI
   - `AttachmentCard.tsx` - Individual attachment display

3. **Outline Mobile Patterns**: https://github.com/outline/outline/blob/main/app/editor/components/
   - `FloatingToolbar.tsx` - Mobile-responsive toolbar
   - `SelectionToolbar.tsx` - Context-aware formatting

---

## Next Steps

1. **Read full research**: See `NOTEBOOK_RESEARCH.md` for detailed analysis
2. **Create editor component**: Start with textarea + markdown
3. **Add health metadata**: Severity, treatment, mood, location
4. **Implement file uploads**: Use Memos patterns
5. **Add audio recording**: Use MediaRecorder API
6. **Test on mobile**: Ensure responsive design works

---

**Decision Made**: April 17, 2026  
**Status**: Ready for implementation  
**Confidence**: High (based on 58K+ GitHub stars for Memos pattern)
