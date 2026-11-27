/** 后端公开的模板和大纲字段；对象标识必须原样回传。 */
export type Template = { object_key: string; file_name: string; size_bytes: number; last_modified: string | null }
export type Outline = { title: string; slides: { role: string; title: string; bullets: { content: string; point_ids: string[] }[] }[] }
export type Question = { question: string; reason: string; options: string[]; allow_free_text: boolean }
export type ChatResult = { task_id: string; status: 'completed' | 'awaiting_user' | 'interrupted'; notice: string; outline: Outline | null; outline_error: string | null; waiting_question: Question | null }
export type StreamEvent = { event: string; data: Record<string, unknown> }
