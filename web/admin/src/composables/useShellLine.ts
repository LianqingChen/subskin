/** 跟踪网页终端里「当前正在输入的那一行」。
 *
 * xterm 只能告诉我们按键字节，拿不到 readline 的行缓冲，所以这里按
 * emacs 模式 readline 的常见按键做**近似**重建：足够支撑「自然语言就地转换」
 * 与「AI 补全」，但不是权威值。
 *
 * 一旦遇到无法还原的操作（Tab 补全、上下键翻历史、Ctrl+R 搜索、粘贴多行等），
 * 就把 ``trusted`` 置为 false —— 此时不再发起 AI 建议，避免基于错误的行做补全。
 * 下一次回车提交后重新变为可信。
 */

const CSI_RE = /\x1b\[[0-9;?]*[a-zA-Z]|\x1b[=>]|\x1b\][^\x07]*\x07|\x1b\[3~|\x1b\[1;5[CD]/
const PASTE_START = '\x1b[200~'
const PASTE_END = '\x1b[201~'

export function isNaturalLanguageLine(line: string): boolean {
  const text = line.trim()
  if (!text) return false
  if (text.startsWith('#') || text.startsWith('?')) return true
  return /[\u4e00-\u9fff]/.test(text)
}

export function useShellLine() {
  let buffer: string[] = []
  let cursor = 0
  // 行内容是否可信（false 表示发生过我们无法还原的编辑）
  let trustworthy = true

  function reset() {
    buffer = []
    cursor = 0
    trustworthy = true
  }

  function currentLine(): string {
    return buffer.join('')
  }

  function insert(text: string) {
    const chars = Array.from(text)
    buffer.splice(cursor, 0, ...chars)
    cursor += chars.length
  }

  function killToEnd() {
    buffer.splice(cursor)
  }

  function deleteWordBefore() {
    let index = cursor
    while (index > 0 && buffer[index - 1] === ' ') index -= 1
    while (index > 0 && buffer[index - 1] !== ' ') index -= 1
    buffer.splice(index, cursor - index)
    cursor = index
  }

  /**
   * 喂入一段终端输入。
   *
   * Returns:
   *   ``{ submitted }`` —— 本次是否提交了一行（回车），以及提交的内容。
   */
  function feed(data: string): { submitted: string | null } {
    if (!data) return { submitted: null }
    let submitted: string | null = null
    let text = data

    // 括号粘贴：整段内容按字面插入
    while (text.includes(PASTE_START)) {
      const start = text.indexOf(PASTE_START)
      const end = text.indexOf(PASTE_END, start)
      insert(text.slice(0, start))
      if (end === -1) {
        insert(text.slice(start + PASTE_START.length))
        text = ''
      } else {
        insert(text.slice(start + PASTE_START.length, end))
        text = text.slice(end + PASTE_END.length)
      }
    }

    for (let index = 0; index < text.length; index += 1) {
      const char = text[index]

      if (char === '\x1b') {
        const rest = text.slice(index)
        const match = rest.match(CSI_RE)
        if (match && match.index === 0) {
          const seq = match[0]
          index += seq.length - 1
          if (seq.endsWith('[D')) cursor = Math.max(0, cursor - 1)
          else if (seq.endsWith('[C')) cursor = Math.min(buffer.length, cursor + 1)
          else if (seq.endsWith('[H') || seq.endsWith('[1~')) cursor = 0
          else if (seq.endsWith('[F') || seq.endsWith('[4~')) cursor = buffer.length
          else if (seq.endsWith('[3~')) buffer.splice(cursor, 1)
          else trustworthy = false // 上下键翻历史、Ctrl+R、其它未识别序列
          continue
        }
        // 裸 ESC（Alt 组合等）：保守视为不可信
        trustworthy = false
        continue
      }

      if (char === '\r' || char === '\n') {
        submitted = currentLine()
        reset()
        continue
      }
      if (char === '\x7f' || char === '\b') {
        if (cursor > 0) {
          buffer.splice(cursor - 1, 1)
          cursor -= 1
        }
        continue
      }
      if (char === '\t') {
        // Tab 会让 shell 改写行缓冲，结果无法预知
        trustworthy = false
        continue
      }
      if (char === '\x03' || char === '\x15') {
        // Ctrl+C / Ctrl+U：清空当前行
        buffer = []
        cursor = 0
        trustworthy = true
        continue
      }
      if (char === '\x0b') {
        killToEnd()
        trustworthy = true
        continue
      }
      if (char === '\x01') {
        cursor = 0
        continue
      }
      if (char === '\x05') {
        cursor = buffer.length
        continue
      }
      if (char === '\x17') {
        deleteWordBefore()
        continue
      }
      if (char === '\x04' || char === '\x12') {
        trustworthy = false
        continue
      }
      if (char < ' ') continue
      insert(char)
    }
    return { submitted }
  }

  /** 外部（AI 采用、填入命令）改写当前行后同步状态。 */
  function override(text: string) {
    buffer = Array.from(text)
    cursor = buffer.length
    trustworthy = true
  }

  return {
    feed,
    override,
    reset,
    currentLine,
    isTrusted: () => trustworthy,
    cursorAtEnd: () => cursor >= buffer.length
  }
}
