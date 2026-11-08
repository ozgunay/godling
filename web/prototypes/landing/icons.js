// Draws the screen's own pixel icons (world/viewer/icons.js) into every [data-icon] of a landing draft.
// Rendering only: the drafts have no behaviour.
import { icon } from '../../../world/viewer/icons.js'

for (const el of document.querySelectorAll('[data-icon]')) {
  el.innerHTML = icon(el.dataset.icon, Number(el.dataset.scale || 3), el.dataset.label || '')
}
