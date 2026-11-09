// The screen's reading of replay's tracks (world/viewer/replay.js reduceStatus) against the cases the guest panel's
// reading of the live log is held to (mind/tests/feed.json, mind/godling/replay.py reduce_status): a replay shows
// Godling's mind as it was shown live.
import { describe, expect, it } from 'vitest'
import CASE from '../../../mind/tests/feed.json'
import { keepLines, lastOf, reduceStatus } from '../../viewer/replay.js'

describe('the mind on the screen', () => {
  it('reads the log as the guest panel does', () => {
    expect(reduceStatus(CASE.entries, CASE.feed_kept, CASE.world_kept)).toEqual(CASE.status)
    for (const moment of ['after_the_first_start', 'while_thinking', 'at_the_start']) {
      expect(reduceStatus(CASE.entries.slice(0, CASE[moment].upto)).now).toEqual(CASE[moment].now)
    }
    const { crowded } = CASE
    expect(reduceStatus(crowded.entries, crowded.feed_kept, crowded.world_kept).feed).toEqual(crowded.feed)
  })

  it('shows a stop-gap with no step of the agenda (ADR-030)', () => {
    expect(reduceStatus(CASE.stopgap.entries).now).toEqual(CASE.stopgap.now)
  })

  it('keeps half of the feed for Godling when the world is busy', () => {
    const entries = [{ time: 1, kind: 'decision', thought: 'Hm.', needs: '' },
      ...Array.from({ length: 20 }, (_, i) => ({ time: 2 + i, kind: 'event', text: `Coconut_${i} appeared` }))]
    const { feed } = reduceStatus(entries)
    expect(feed).toHaveLength(5)
    expect(feed[0].text).toBe('Hm.')
    expect(feed[feed.length - 1].text).toBe('Coconut_19 appeared')
    expect(reduceStatus(entries, 5).feed).toHaveLength(1 + 2) // half of a shorter feed, rounded down, as reduce_status
  })

  it('keeps the screen\'s fewer lines by the same rule', () => {
    const line = (who, text, about) => ({ who, text, about })
    const feed = [line('godling', 'Old plan.'), line('godling', 'A', 'failed'), line('notice', 'n1'), line('godling', 'B', 'failed'),
      line('notice', 'n2'), line('sky', 's3')]
    expect(keepLines(feed, 3, 1).map((l) => l.text)).toEqual(['Old plan.', 'B', 's3'])
    expect(lastOf(feed, (l) => l.who === 'notice').text).toBe('n2')
    expect(lastOf([], () => true)).toBeUndefined()
  })
})
