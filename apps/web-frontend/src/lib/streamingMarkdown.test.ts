import { describe, expect, it } from 'vitest'
import { splitStreamingMarkdown } from '@/lib/streamingMarkdown'

describe('splitStreamingMarkdown', () => {
  it('treats plain prose as fully stable', () => {
    expect(splitStreamingMarkdown('Атака ближнего боя добавляет **СИЛ**')).toEqual({
      stable: 'Атака ближнего боя добавляет **СИЛ**',
      pending: '',
    })
  })

  it('holds back an unfinished fence so the rest of the message stays a giant code block', () => {
    const result = splitStreamingMarkdown('Пример:\n\n```js\nconst x = 1')
    expect(result).toEqual({ stable: 'Пример:\n\n', pending: '```js\nconst x = 1' })
  })

  it('releases the fence once it closes', () => {
    const result = splitStreamingMarkdown('Пример:\n\n```js\nconst x = 1\n```\n\nДальше текст')
    expect(result).toEqual({
      stable: 'Пример:\n\n```js\nconst x = 1\n```\n\nДальше текст',
      pending: '',
    })
  })

  it('holds back a second fence even once an earlier one closed', () => {
    const result = splitStreamingMarkdown('```js\nconst x = 1\n```\n\nЕщё пример:\n\n```py\nx = 1')
    expect(result).toEqual({
      stable: '```js\nconst x = 1\n```\n\nЕщё пример:\n\n',
      pending: '```py\nx = 1',
    })
  })

  it('holds back everything when a message opens with a fence', () => {
    const result = splitStreamingMarkdown('```js\nconst x = 1')
    expect(result).toEqual({ stable: '', pending: '```js\nconst x = 1' })
  })
})
