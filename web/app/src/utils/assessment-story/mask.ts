/** Pure geometry from the reviewed mask; never edits the source measurement. */
export interface StoryShape {
  width: number; height: number; pixels: Uint8Array
  bounds: { x: number; y: number; width: number; height: number }
  count: number; clusters: number; area: number
  kind: 'scattered' | 'vertical' | 'horizontal' | 'compact'
}
export function analyzeStoryMask(rgba: Uint8ClampedArray, width: number, height: number): StoryShape | null {
  if (!Number.isInteger(width) || !Number.isInteger(height) || width < 1 || height < 1 || width * height > 16777216 || rgba.length !== width * height * 4) return null
  let transparent = false, grayscale = true
  for (let i = 0; i < rgba.length; i += 4) {
    if (rgba[i + 3] < 255) transparent = true
    if (rgba[i] !== rgba[i + 1] || rgba[i] !== rgba[i + 2]) grayscale = false
  }
  // Opaque colour overlays cannot reliably distinguish their background.
  if (!transparent && !grayscale) return null
  const pixels = new Uint8Array(width * height)
  let x0 = width, y0 = height, x1 = -1, y1 = -1, area = 0
  for (let i = 0; i < pixels.length; i++) {
    if ((transparent ? rgba[i * 4 + 3] : rgba[i * 4]) <= 32) continue
    pixels[i] = 1; area++
    const x = i % width, y = Math.floor(i / width)
    x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y)
  }
  if (!area) return null
  const visited = new Uint8Array(pixels.length), queue = new Int32Array(area), sizes: number[] = []
  for (let i = 0; i < pixels.length; i++) {
    if (!pixels[i] || visited[i]) continue
    let head = 0, tail = 1; queue[0] = i; visited[i] = 1
    while (head < tail) {
      const p = queue[head++], px = p % width, py = Math.floor(p / width)
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
        const x = px + dx, y = py + dy, n = y * width + x
        if (x < 0 || y < 0 || x >= width || y >= height || !pixels[n] || visited[n]) continue
        visited[n] = 1; queue[tail++] = n
      }
    }
    sizes.push(tail)
  }
  const bounds = { x: x0, y: y0, width: x1 - x0 + 1, height: y1 - y0 + 1 }
  const clusters = sizes.filter(size => size >= Math.max(1, area * 0.005)).length
  const ratio = bounds.width / bounds.height
  return { width, height, pixels, bounds, count: sizes.length, clusters, area,
    kind: clusters >= 3 ? 'scattered' : ratio < 0.65 ? 'vertical' : ratio > 1.65 ? 'horizontal' : 'compact' }
}
