// Browser events for the tests: jsdom has no PointerEvent, so pointer events are mouse events with an id and a kind.
export function pointer(type, { x = 0, y = 0, id = 1, kind = 'mouse' } = {}) {
  const event = new MouseEvent(type, { bubbles: true, cancelable: true, clientX: x, clientY: y })
  Object.defineProperty(event, 'pointerId', { value: id })
  Object.defineProperty(event, 'pointerType', { value: kind })
  return event
}

export function key(type, code, extra = {}) {
  return new KeyboardEvent(type, { code, key: extra.key ?? code, bubbles: true, cancelable: true, ...extra })
}

export function wheel(deltaY) {
  return new WheelEvent('wheel', { deltaY, bubbles: true, cancelable: true })
}

// A canvas laid out at 100 x 100 pixels, as the island's would be.
export function canvas() {
  const c = document.createElement('canvas')
  c.getBoundingClientRect = () => ({ left: 0, top: 0, width: 100, height: 100, right: 100, bottom: 100 })
  document.body.append(c)
  return c
}
