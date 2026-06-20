# Open-Source Notebook/Journal Apps: Editor & Media Handling Research

**Research Date**: April 2026  
**Focus**: Rich content creation, media handling, mobile UX for health journaling platforms

---

## Executive Summary

Three leading open-source notebook projects analyzed:

| Project | Editor | Tech Stack | Best For |
|---------|--------|-----------|----------|
| **Outline** | ProseMirror-based | React + TypeScript + Node.js | Team knowledge bases, collaborative editing |
| **Memos** | Plain textarea + Markdown | React 18 + Go backend | Quick capture, timeline-first, minimal UI |
| **SiYuan** | Block-style WYSIWYG (Protyle) | TypeScript + Go + Electron | Personal knowledge management, local-first |

---

## 1. OUTLINE (getoutline.com)

### Editor Architecture
- **Editor**: Custom **ProseMirror-based** rich text editor (`shared/editor/`)
- **Framework**: React + TypeScript (Vite)
- **State Management**: MobX for editor state
- **Styling**: Styled Components

**Key Implementation**:
```typescript
// From: app/editor/index.tsx
import { EditorView } from "prosemirror-view";
import insertFiles from "@shared/editor/commands/insertFiles";
import ExtensionManager from "@shared/editor/lib/ExtensionManager";

// ProseMirror plugins for tables, diagrams, comments
import { FixTablesPlugin } from "@shared/editor/plugins/FixTablesPlugin";
import { CommentedImagePlugin } from "@shared/editor/plugins/CommentedImagePlugin";
```

### Content Blocks & Structure
- **Block-style editing** with floating toolbar
- **Selection toolbar** for formatting (bold, italic, links, etc.)
- **Floating toolbar** for node-level operations (images, tables, embeds)
- **Collaborative editing** via Y.js (real-time sync)

**Evidence** ([FloatingToolbar.tsx](https://github.com/outline/outline/blob/main/app/editor/components/FloatingToolbar.tsx)):
```typescript
import { NodeSelection } from "prosemirror-state";
import { Portal } from "~/components/Portal";
import useMobile from "~/hooks/useMobile";

// Floating toolbar adapts to mobile via useMobile hook
const FloatingToolbar = () => {
  const isMobile = useMobile();
  // Toolbar repositions on mobile devices
};
```

### Media Handling
- **Image insertion**: Via `insertFiles` command
- **Paste handling**: Custom `PasteHandler` extension normalizes markdown
- **Drag & drop**: Supported through ProseMirror plugins
- **Image comments**: `CommentedImagePlugin` decorates images with comment marks

**Evidence** ([PasteHandler.tsx](https://github.com/outline/outline/blob/main/app/editor/extensions/PasteHandler.tsx)):
```typescript
import { Plugin, PluginKey } from "prosemirror-state";
import normalizePastedMarkdown from "@shared/editor/lib/markdown/normalize";

// Handles paste events with markdown normalization
export default class PasteHandler extends Extension {
  // Normalizes pasted markdown, handles code blocks, links
}
```

### Mobile UX Patterns
- **Responsive toolbar**: Floating toolbar repositions on mobile
- **Touch-friendly**: Uses `useMobile` hook to adapt UI
- **Portal-based menus**: Menus render outside DOM hierarchy for better mobile positioning
- **Selection handling**: Adapted for touch selection

**Evidence** ([SelectionToolbar.tsx](https://github.com/outline/outline/blob/main/app/editor/components/SelectionToolbar.tsx)):
```typescript
import { Portal } from "~/components/Portal";
import useMobile from "~/hooks/useMobile";

// Portal ensures menus don't get clipped on mobile
const SelectionToolbar = () => {
  const isMobile = useMobile();
  return <Portal>{/* toolbar content */}</Portal>;
};
```

### Key Features Worth Adopting
✅ **ProseMirror plugin system** - Extensible, battle-tested  
✅ **Collaborative editing** - Y.js integration for real-time sync  
✅ **Floating/Selection toolbars** - Context-aware formatting  
✅ **Markdown serialization** - Full markdown import/export  
✅ **Comment system** - Inline comments on any content  
✅ **Table support** - Complex table editing with plugins  

### Limitations for Health Journaling
❌ Heavy (React + ProseMirror bundle)  
❌ Requires backend server  
❌ Not optimized for quick capture  
❌ Collaborative features may be overkill for personal journaling  

---

## 2. MEMOS (usememos.com)

### Editor Architecture
- **Editor**: Plain `<textarea>` with Markdown syntax
- **Framework**: React 18 + TypeScript (Vite)
- **State Management**: React Query v5 + React Context
- **Backend**: Go (Echo v5 router) + SQLite/MySQL/PostgreSQL
- **API**: Dual protocol (Connect RPC + gRPC-Gateway)

**Key Implementation**:
```typescript
// From: web/src/components/MemoEditor/Editor/index.tsx
const Editor = forwardRef(function Editor(props: EditorProps, ref: React.ForwardedRef<EditorRefActions>) {
  const editorRef = useRef<HTMLTextAreaElement>(null);
  
  const getCursorLineNumber = () => number;
  const getLine = (lineNumber: number) => string;
  const setLine = (lineNumber: number, text: string) => void;
  
  // Simple textarea with line-based operations
});
```

### Content Blocks & Structure
- **Timeline-first UI**: No folders, just a feed of memos
- **Markdown-native**: All content stored as plain Markdown
- **Minimal structure**: No block-level nesting (unlike Notion/SiYuan)
- **Task lists**: Markdown checkboxes `- [ ]`
- **Tags**: `#tag` syntax for organization

**Evidence** ([MemoEditor/index.tsx](https://github.com/usememos/memos/blob/main/web/src/components/MemoEditor/index.tsx)):
```typescript
// Timeline-first, no complex block structure
const MemoEditor = (props: MemoEditorProps) => (
  <EditorProvider>
    <MemoEditorImpl {...props} />
  </EditorProvider>
);

// Supports audio recording, attachments, location metadata
const MemoEditorImpl: React.FC<MemoEditorProps> = ({
  className,
  cacheKey,
  placeholder,
  memo,
  autoFocus,
  onConfirm,
});
```

### Media Handling
- **Audio recording**: Built-in `useAudioRecorder` hook with live waveform
- **File uploads**: `useFileUpload` hook with drag-and-drop support
- **Attachments**: Separate `AttachmentListEditor` component
- **Image preview**: `PreviewImageDialog` for viewing images
- **Blob URLs**: `useBlobUrls` hook for client-side preview URLs

**Evidence** ([useFileUpload.ts](https://github.com/usememos/memos/blob/main/web/src/components/MemoEditor/hooks/useFileUpload.ts)):
```typescript
export const useFileUpload = (onFilesSelected: (localFiles: LocalFile[]) => void) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const selectingFlagRef = useRef(false);

  const handleFileInputChange = (event?: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(fileInputRef.current?.files || event?.target.files || []);
    // Convert to LocalFile with preview URLs
    const localFiles: LocalFile[] = files.map((file) => ({
      file,
      previewUrl: createBlobUrl(file),
      origin: "upload",
    }));
    onFilesSelected(localFiles);
  };
};
```

**Audio Recording** ([AudioRecorderPanel.tsx](https://github.com/usememos/memos/blob/main/web/src/components/MemoEditor/components/AudioRecorderPanel.tsx)):
```typescript
export const AudioRecorderPanel: FC<AudioRecorderPanelProps> = ({
  audioRecorder,
  mediaStream,
  onStop,
  onCancel,
  onTranscribe,
}) => {
  // Live waveform visualization during recording
  const { waveformData } = useAudioWaveform(mediaStream);
  
  return (
    <div>
      <VoiceWaveform data={waveformData} />
      <Button onClick={onStop}>Stop Recording</Button>
      <Button onClick={onTranscribe}>Transcribe with AI</Button>
    </div>
  );
};
```

**Drag & Drop** ([useDragAndDrop.ts](https://github.com/usememos/memos/blob/main/web/src/components/MemoEditor/hooks/useDragAndDrop.ts)):
```typescript
export function useDragAndDrop(onDrop: (files: FileList) => void) {
  return {
    dragHandlers: {
      onDragOver: (e: React.DragEvent) => {
        if (e.dataTransfer?.types.includes("Files")) {
          e.preventDefault();
          // Visual feedback for drag-over
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

**Attachment Management** ([AttachmentListEditor.tsx](https://github.com/usememos/memos/blob/main/web/src/components/MemoMetadata/Attachment/AttachmentListEditor.tsx)):
```typescript
interface AttachmentListEditorProps {
  attachments: Attachment[];
  localFiles?: LocalFile[];
  onAttachmentsChange?: (attachments: Attachment[]) => void;
  onLocalFilesChange?: (localFiles: LocalFile[]) => void;
  onRemoveLocalFile?: (previewUrl: string) => void;
}

// Separate UI for managing attachments (images, audio, files)
// Shows preview thumbnails, file size, type labels
```

### Mobile UX Patterns
- **Responsive layout**: Tailwind CSS v4 for mobile-first design
- **Touch-friendly input**: Soft keyboard toolbar on Android/iOS
- **Simplified editor**: Plain textarea works well on mobile
- **Metadata sidebar**: Collapses on mobile
- **Focus mode**: Full-screen editor for distraction-free writing

**Evidence** ([MemoEditor/index.tsx](https://github.com/usememos/memos/blob/main/web/src/components/MemoEditor/index.tsx)):
```typescript
// Focus mode for mobile
const isAudioRecorderOpen = state.audioRecorder.status === "recording";

// Metadata section (attachments, location, relations) adapts to mobile
<EditorMetadata memoName={memoName} />

// Soft keyboard toolbar on mobile
// Input method compatibility for IME (Chinese, Japanese, etc.)
```

### Key Features Worth Adopting
✅ **Lightweight textarea editor** - Fast, minimal dependencies  
✅ **Audio recording with transcription** - Perfect for health journaling  
✅ **Drag-and-drop file upload** - Intuitive media handling  
✅ **Blob URL previews** - Client-side preview before upload  
✅ **Metadata separation** - Attachments, location, relations in sidebar  
✅ **Timeline-first UX** - No folder navigation overhead  
✅ **Markdown-native** - Portable, future-proof format  
✅ **Focus mode** - Distraction-free writing  
✅ **AI transcription** - Convert audio to text  

### Ideal For Health Journaling
✅ Quick capture (open, write, done)  
✅ Audio journaling (voice notes → transcription)  
✅ Lightweight on mobile  
✅ Privacy-first (self-hosted)  
✅ Minimal UI (less cognitive load for patients)  

---

## 3. SIYUAN (b3log.org/siyuan)

### Editor Architecture
- **Editor**: **Protyle** - Custom WYSIWYG block editor
- **Framework**: TypeScript + Electron (desktop) + React (mobile)
- **Backend**: Go kernel with local-first architecture
- **Markdown Engine**: **Lute** (custom Go markdown parser)
- **Storage**: SQLite (local) + optional cloud sync

**Key Implementation**:
```typescript
// From: app/src/protyle/index.ts
export class Protyle {
  public readonly version: string;
  public protyle: IProtyle;
  
  // WYSIWYG editing system with block-level operations
  // Supports undo/redo via transaction system
}

// From: app/src/util/functions.ts
export const isMobile = () => {
  return document.getElementById("sidebar") ? true : false;
};
```

### Content Blocks & Structure
- **Block-style editing**: Each paragraph, heading, list item is a block
- **Block references**: Link to any block via `((block-id))`
- **Two-way links**: Bidirectional references between blocks
- **Nested blocks**: Indent/outdent to create hierarchies
- **Block zoom**: Focus on single block or expand context
- **Database views**: Table, kanban, gallery views for structured data

**Evidence** ([WYSIWYG System](https://deepwiki.com/siyuan-note/siyuan/4.2.1-wysiwyg-editing-system)):
```typescript
// Block-level operations
// - Enter: Create new block
// - /: Slash commands for block types
// - Indent/Outdent: Nest blocks
// - Transaction system: Undo/redo with full history

// Supports:
// - Markdown WYSIWYG (live preview)
// - Code blocks with syntax highlighting
// - Tables with cell editing
// - Math formulas (LaTeX)
// - Diagrams (Mermaid, PlantUML)
// - Callouts, toggles, quotes
```

### Media Handling
- **Asset management**: Dedicated asset folder per document
- **Image insertion**: Drag-drop or paste images
- **OCR support**: Tesseract OCR for image text extraction
- **Audio/Video**: Embed media files
- **File attachments**: Any file type supported
- **Sync**: Assets sync with document via cloud service

**Evidence** ([Mobile Asset Editing](https://github.com/siyuan-note/siyuan/releases/tag/v3.5.8)):
```
- Improve the database asset editing UI on mobile
- Improve batch pasting of images into the database
- Support copying file in the asset menu on Windows and macOS
- Assets cannot be exported on Windows (fixed)
```

### Mobile UX Patterns
- **Native mobile apps**: iOS/Android/HarmonyOS apps (not web)
- **Responsive UI**: Adapts to small screens
- **Touch gestures**: Swipe, long-press for block operations
- **Soft keyboard**: Input method toolbar on mobile
- **Simplified toolbar**: Fewer buttons on mobile
- **Sidebar collapse**: Sidebar hides on mobile to maximize editor space

**Evidence** ([Mobile Improvements](https://github.com/siyuan-note/siyuan/releases/tag/v3.5.5)):
```
- Support input method toolbar on mobile browser
- Improve detection of sidebar panel sliding out on mobile
- Improve soft keyboard toolbar pop-up on Android and HarmonyOS
- Adapt to Apple's dark APP icon on iOS
- Improve Ctrl+Shift+T open recently closed documents
- Improve heading block copying on Android and HarmonyOS
```

### Key Features Worth Adopting
✅ **Block-style editing** - Flexible, composable content structure  
✅ **Block references** - Link to any piece of content  
✅ **Two-way links** - Automatic backlinks  
✅ **Database views** - Table, kanban, gallery for structured data  
✅ **Local-first architecture** - Data stays on device  
✅ **Markdown WYSIWYG** - Edit markdown with live preview  
✅ **OCR support** - Extract text from images  
✅ **Native mobile apps** - Better performance than web  
✅ **Spaced repetition** - Flashcard system for learning  

### Limitations for Health Journaling
❌ Complex UI (steep learning curve for patients)  
❌ Requires Electron/native app (not web-based)  
❌ Heavy feature set (may overwhelm casual users)  
❌ Block-level nesting can be confusing for simple journaling  

---

## Comparison Matrix

| Feature | Outline | Memos | SiYuan |
|---------|---------|-------|--------|
| **Editor Type** | ProseMirror (rich text) | Textarea (markdown) | Protyle (block WYSIWYG) |
| **Learning Curve** | Medium | Low | High |
| **Mobile Support** | Web responsive | Web responsive | Native apps |
| **Collaboration** | ✅ Real-time (Y.js) | ❌ Single-user | ❌ Single-user |
| **Audio Recording** | ❌ | ✅ Built-in | ✅ Supported |
| **File Uploads** | ✅ Via paste/drag | ✅ Drag-drop + upload | ✅ Asset folder |
| **Block References** | ❌ | ❌ | ✅ Full support |
| **Database Views** | ❌ | ❌ | ✅ Table/Kanban/Gallery |
| **Local-first** | ❌ (server required) | ✅ (self-hosted) | ✅ (local + sync) |
| **Markdown Native** | ✅ | ✅ | ✅ |
| **Bundle Size** | Large | Small | Large (Electron) |
| **Best For** | Teams, knowledge bases | Quick capture, journaling | Personal knowledge mgmt |

---

## Recommendations for Vitiligo Community Platform

### Recommended Approach: **Hybrid Memos + Custom Blocks**

**Why Memos as foundation?**
1. **Lightweight** - Fast on mobile (critical for patient engagement)
2. **Audio journaling** - Perfect for health tracking ("How I'm feeling today...")
3. **Minimal UI** - Less cognitive load for patients
4. **Self-hosted** - Privacy for sensitive health data
5. **Markdown-native** - Portable, future-proof

**Enhancements to add:**
1. **Block-style metadata** (from SiYuan):
   - Vitiligo severity (0-10 scale)
   - Treatment applied
   - Photos before/after
   - Mood/stress level
   - Location of patches

2. **Rich media handling** (from Memos):
   - Audio recording for voice journaling
   - Image upload with before/after comparison
   - File attachments (medical reports, prescriptions)

3. **Collaborative features** (from Outline):
   - Comments from dermatologists
   - Shared insights with support group
   - Floating toolbar for quick formatting

### Tech Stack Recommendation

```typescript
// Frontend
- React 18 + TypeScript
- Vite for bundling
- Tailwind CSS v4 for responsive design
- React Query v5 for data fetching
- Zustand or Context API for state

// Editor
- Textarea + Markdown (Memos approach)
- Custom block components for health metadata
- Tiptap v2 (Vue 3 compatible) if you need rich text later

// Media Handling
- Drag-and-drop with useDragAndDrop hook
- Blob URLs for client-side preview
- Separate AttachmentListEditor component
- Audio recording with MediaRecorder API

// Backend
- Go (Echo v5) or Node.js (Express)
- SQLite for local storage
- S3/Cloudflare R2 for media storage
- gRPC + Connect RPC for API

// Mobile
- React Native or web-responsive design
- Native audio recording (MediaRecorder API)
- Touch-friendly UI (Memos pattern)
```

### Implementation Priority

**Phase 1 (MVP)**:
- Textarea editor with Markdown
- Image upload + preview
- Metadata sidebar (severity, treatment, mood)
- Mobile-responsive design

**Phase 2**:
- Audio recording + transcription
- Before/after image comparison
- Timeline view (Memos-style)
- Basic search

**Phase 3**:
- Comments from healthcare providers
- Shared insights with support group
- Data export (PDF, CSV)
- Advanced analytics

---

## Code Examples for Your Implementation

### 1. File Upload Hook (Memos Pattern)

```typescript
// hooks/useFileUpload.ts
import { useRef } from "react";

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

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  return {
    fileInputRef,
    handleFileInputChange,
    handleUploadClick,
  };
};
```

### 2. Drag & Drop Handler (Memos Pattern)

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
        if (e.dataTransfer?.files) {
          onDrop(e.dataTransfer.files);
        }
      },
    },
  };
}
```

### 3. Audio Recording (Memos Pattern)

```typescript
// hooks/useAudioRecorder.ts
import { useRef, useState } from "react";

export const useAudioRecorder = () => {
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const [recordingStream, setRecordingStream] = useState<MediaStream | null>(null);
  const [status, setStatus] = useState<"idle" | "recording" | "requesting_permission">("idle");

  const startRecording = async () => {
    setStatus("requesting_permission");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      setRecordingStream(stream);
      
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      
      const chunks: BlobPart[] = [];
      mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
      mediaRecorder.onstop = () => {
        const blob = new Blob(chunks, { type: "audio/webm" });
        // Handle audio blob
      };
      
      mediaRecorder.start();
      setStatus("recording");
    } catch (error) {
      console.error("Microphone access denied", error);
      setStatus("idle");
    }
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    recordingStream?.getTracks().forEach((track) => track.stop());
    setStatus("idle");
  };

  return { startRecording, stopRecording, recordingStream, status };
};
```

### 4. Metadata Editor Component

```typescript
// components/HealthMetadataEditor.tsx
import { FC } from "react";

interface HealthMetadata {
  severity: number; // 0-10
  treatment: string;
  mood: number; // 0-10
  location: string;
  notes: string;
}

export const HealthMetadataEditor: FC<{
  metadata: HealthMetadata;
  onChange: (metadata: HealthMetadata) => void;
}> = ({ metadata, onChange }) => {
  return (
    <div className="space-y-4 p-4 bg-gray-50 rounded-lg">
      <div>
        <label>Vitiligo Severity (0-10)</label>
        <input
          type="range"
          min="0"
          max="10"
          value={metadata.severity}
          onChange={(e) =>
            onChange({ ...metadata, severity: parseInt(e.target.value) })
          }
        />
        <span>{metadata.severity}/10</span>
      </div>

      <div>
        <label>Treatment Applied</label>
        <input
          type="text"
          value={metadata.treatment}
          onChange={(e) => onChange({ ...metadata, treatment: e.target.value })}
          placeholder="e.g., Topical steroid, phototherapy"
        />
      </div>

      <div>
        <label>Mood (0-10)</label>
        <input
          type="range"
          min="0"
          max="10"
          value={metadata.mood}
          onChange={(e) => onChange({ ...metadata, mood: parseInt(e.target.value) }) }
        />
        <span>{metadata.mood}/10</span>
      </div>

      <div>
        <label>Affected Location</label>
        <input
          type="text"
          value={metadata.location}
          onChange={(e) => onChange({ ...metadata, location: e.target.value })}
          placeholder="e.g., Face, hands, legs"
        />
      </div>
    </div>
  );
};
```

---

## References

- **Outline**: https://github.com/outline/outline (38K stars)
  - Architecture: https://github.com/outline/outline/blob/main/docs/ARCHITECTURE.md
  - Rich Markdown Editor: https://github.com/outline/rich-markdown-editor

- **Memos**: https://github.com/usememos/memos (58K stars)
  - Architecture: https://usememos.com/docs/operations/architecture
  - MemoEditor: https://github.com/usememos/memos/blob/main/web/src/components/MemoEditor/

- **SiYuan**: https://github.com/siyuan-note/siyuan (42K stars)
  - WYSIWYG System: https://deepwiki.com/siyuan-note/siyuan/4.2.1-wysiwyg-editing-system
  - Releases: https://github.com/siyuan-note/siyuan/releases

---

**Document Version**: 1.0  
**Last Updated**: April 17, 2026
