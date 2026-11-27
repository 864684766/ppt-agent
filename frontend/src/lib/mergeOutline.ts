import type { Outline } from '../api/contracts'

/** 后端续轮包含历史资料；保留已有页面，仅将未出现过的来源要点追加为新页面。 */
export function mergeOutline(previous: Outline | null, incoming: Outline): Outline {
  if (!previous) return incoming
  const seen = new Set(previous.slides.flatMap((slide) => slide.bullets.flatMap((bullet) => bullet.point_ids)))
  const slides = incoming.slides.flatMap((slide) => {
    const bullets = slide.bullets.filter((bullet) => bullet.point_ids.some((id) => !seen.has(id)))
    for (const bullet of bullets) for (const id of bullet.point_ids) seen.add(id)
    return bullets.length ? [{ ...slide, bullets }] : []
  })
  return { ...previous, slides: [...previous.slides, ...slides] }
}
