/** Shared coordinates for the poster and the sticker landing animation. */
export function storyArtworkRect(bounds: { width: number; height: number }, y = 130, height = 830) {
  const scale = Math.min(820 / bounds.width, (height - (height < 400 ? 60 : 90)) / bounds.height)
  const width = bounds.width * scale, imageHeight = bounds.height * scale
  return { x: (1080 - width) / 2, y: y + (height - imageHeight) / 2, width, height: imageHeight, scale }
}
