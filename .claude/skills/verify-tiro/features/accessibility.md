# Accessibility

Keyboard and screen-reader users, people on phones and people who turn off motion can do everything above. The page meets WCAG 2.2 AA on the review screen, moves focus to new results, has no horizontal scroll at 390 px, and stops animating under reduced motion.

## Sub-features

- `axe` axe-core finds no WCAG 2.0/2.1/2.2 A or AA violations on the review screen.
- `focus` focus moves to `#results-heading` on start, on review and on Done (covered in the other journeys).
- `mobile` 390x844 has no horizontal scroll.
- `reduced-motion` with `prefers-reduced-motion: reduce` no animation is running after load.
- `live-progress` the results summary is an `aria-live="polite"` region announcing progress.

## How to get to it (user POV)

- Use the site with a keyboard only (Tab, Enter, Escape), a screen reader, a phone, or the OS "reduce motion" setting.

## Driving it with tiro.mjs

Preconditions:

- Baseline from the index.

- **Axe.** Run `node .claude/skills/verify-tiro/scripts/tiro.mjs journey accessibility`. It reaches the review, injects `axe-core/axe.min.js` from `apps/web/node_modules`, runs the WCAG tags and writes `axe-review.json`; any violation fails.
- **Mobile.** It opens a 390x844 page and checks `scrollWidth <= innerWidth`. Proof: `1-mobile-start.png`.
- **Reduced motion.** It opens a context with `reducedMotion: "reduce"` and checks `document.getAnimations()` has nothing running.

## Gotchas

- axe checks only what is rendered: the dialog and the Done state are not scanned by this journey; scan them too when changing those views.
- Automated checks do not prove usability with a real screen reader; say so instead of claiming full accessibility.
