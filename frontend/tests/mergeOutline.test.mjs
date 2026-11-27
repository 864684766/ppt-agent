import test from 'node:test'
import assert from 'node:assert/strict'
import { mergeOutline } from '../src/lib/mergeOutline.ts'

const page = (title, id, content = title) => ({ title, role: 'content', bullets: [{ content, point_ids: [id] }] })
test('续轮保留已有编辑，仅追加新来源要点', () => {
  const old = { title: '用户修改的标题', slides: [page('手工修改的页面', 'p1', '手工内容')] }
  const next = { title: '模型标题', slides: [page('旧内容', 'p1'), page('React 面试', 'p2')] }
  const merged = mergeOutline(old, next)
  assert.equal(merged.title, old.title)
  assert.deepEqual(merged.slides, [old.slides[0], next.slides[1]])
  assert.equal(old.slides.length, 1)
})

test('多次预览基于同一旧大纲重算，最终结果不会重复追加', () => {
  const old = { title: '大纲', slides: [page('原有', 'p1')] }
  const preview = { title: '预览', slides: [page('新增', 'p2')] }
  const final = { title: '最终', slides: [page('原有', 'p1'), page('新增', 'p2'), page('更多', 'p3')] }
  assert.equal(mergeOutline(old, preview).slides.length, 2)
  assert.deepEqual(mergeOutline(old, final).slides.map((slide) => slide.title), ['原有', '新增', '更多'])
})
