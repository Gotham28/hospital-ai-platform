# Gothos Labs brand

Gothos Labs makes software perfected by AI. This file says how anything from Gothos Labs
should look and sound. It is a copy of the master: the "Gothos Labs" design system in Claude
(https://claude.ai/artifact/A89eeWqR7oYZnjr7x6kpUo). If this copy and the master disagree,
the master wins; tell the developer so this copy can be updated.

Values come from the company website (gothoslabs.com, styles.css). Nothing here is invented.

## How the brand is set up

- **Gothos Labs** is the company. Its logo is the owl.
- **Each product** (ELogBook, AROGYA, and those still to come) has its own logo and is meant
  to share everything else here: colours, font, shapes, way of writing.
- Every product carries a small "by GOTHOS LABS" line (see "The by-line").
- **Mochi** is the leaf-feathered owl who guides people. Mochi is a character, not a logo.

## What applies now, and what waits

Applies now, in every product:
- Names, spelling and the way we write.
- The owl logo and Mochi artwork: use the real files, never redraw them.
- Anything that speaks as the company: about pages, "by GOTHOS LABS" lines, emails,
  documents, slides, marketing pages.

Waits for its own approved task:
- Changing a product's existing screens to these colours, this font and these shapes.
  Never do this as a side effect of other work. It is a separate task the developer scopes.
- Adding the "by GOTHOS LABS" line to a product's screens.

## How we write

- Short, plain sentences that say what the thing does.
  "A digital logbook for postgraduate medical training."
- Speak as "we" and to "you". "We use AI to perfect the software you rely on."
- Headings are sentence case: "What we do", "Our products", "Talk to us".
- A tagline is a full sentence and ends with a full stop: "Software, perfected by AI."
- British spelling: "organisation", "colour", "enquiry".
- Button labels start with a verb and have no full stop: "Explore ELogBook", "Send enquiry".
- Be honest about limits, in plain words, right where it matters.
  "General information only. It does not diagnose or replace a doctor."
- No emoji. No exclamation marks. No hype words such as "revolutionary".
- Names are written one way only: **Gothos Labs**, **ELogBook** (capital E, L and B),
  **AROGYA** (all capitals), **Mochi**.

## Colour

Green on warm off-white. All values are in `tokens.css` and `tokens.json`.

| Name | Value | Use |
|---|---|---|
| `bg` | #f7f6f1 | Page background. Never pure white, never a dark page. |
| `ink` | #14231b | Body text. Never pure black. |
| `forest` | #1e5b3f | The main brand colour: headings, links, buttons, wordmark. White text on it is fine (8.0:1). |
| `deep` | #123d2b | Hover of a solid button; rare dark bands with white text. |
| `emerald` | #2f8f5b | Shapes only (dots, the short hero rule). Not for small text (3.7:1 on bg). |
| `emerald-text` | #1f7a49 | Green text: taglines, the small uppercase line. On bg or white only. |
| `muted` | #4a5f53 | Helper text, captions, disclaimers, placeholders. |
| `soft-ink` | #3f5448 | Long intro paragraphs. |
| `sage` | #dde9df | Quiet ground for notices and chip hover. |
| `mist` | #eef4ef | Ground of an assistant chat bubble. |
| `mint` | #a9d3b4 | Light accent for shapes. Never text on a light ground. |
| `leaf` | #79a98a | Background leaf shapes at about 20% opacity. |
| `line` | #9eb7a5 | 1px field border on the website. Faint (2.0:1): in busy forms use `muted`. |
| `line-soft` | #c4d6c8 | 1px border of dialogs and menus. |
| `card` | rgba(255,255,255,.64) | Fill of a floating card, over bg. |
| `card-edge` | rgba(255,255,255,.9) | 1px edge of a floating card. |
| `focus` | #33824e | Keyboard focus ring. |
| `scrim` | #173c2c50 | Dim layer behind a dialog, with a 10px blur. |

- The only gradient is the short hero rule, `emerald` to `mint`. No second accent colour.
- One theme: light. A dark theme is not defined.

## Type

One font family: **Poppins**, weights 300 to 800 (SIL Open Font License).

| Style | Size / line height | Weight | Notes |
|---|---|---|---|
| hero | clamp(40px, min(7.4vw,12.4vh), 118px) / 1.04 | 800 | letter-spacing -0.05em, forest. One per page. |
| title | clamp(34px, min(5.6vw,9.4vh), 84px) / 1.06 | 700 | -0.035em, forest |
| tagline | clamp(17px, min(1.9vw,3.4vh), 26px) / 1.3 | 500 | -0.015em, emerald-text |
| lede | clamp(13.5px, min(1.18vw,2.2vh), 18px) / 1.7 | 400 | soft-ink, max 520px wide |
| eyebrow | clamp(14px, min(1.5vw,2.6vh), 22px) | 600 | 0.14em, uppercase, emerald-text |
| product-name | clamp(20px, min(2.4vw,4.2vh), 32px) / 1.15 | 700 | -0.03em, forest |
| heading | 24px / 1.12 | 600 | dialogs and pages inside a product |
| subheading | 16px / 1.12 | 600 | panel headings |
| body | 15px / 1.6 | 400 | default text, ink |
| button | 13px / 1.4 | 600 | |
| label | 11px / 1.6 | 500 | above a field |
| small | 11px / 1.7 | 400 | muted. Nothing is smaller than this. |

- For screens people read all day (tables, chat), do not go below 12px; prefer `body`.
- Poppins has no Malayalam letters. Set Malayalam text in Noto Sans Malayalam.

## Shape, depth and space

- Everything is rounded. Buttons and chips are full pills (999px). Cards and dialogs 24px.
  Large panels 28px. Screenshots 18px. Chat bubbles 14px. Fields 9px.
- Cards float: `card` fill, `card-edge` border, shadow `0 30px 80px rgba(30,91,63,.12)`.
  Shadows are tinted forest green, never grey or black.
- Borders are 1px and pale green. The outline button border is 1.8px.

## Building blocks

- **Button.** A pill. Padding 12px 22px, Poppins 600 13px. Solid: forest fill, white text,
  hover deep. Outline: forest text, 1.8px border, hover fills forest. Both lift 2px on
  hover. Disabled is 68% opacity. One solid button per view.
- **Card.** See "Shape, depth and space". Padding up to 26px 30px. A link card lifts 3px
  and takes shadow `0 34px 80px rgba(30,91,63,.2)`.
- **Field.** Label above (11px, weight 500), control at least 40px tall, padding 9px 12px,
  1px border, 9px corners. The label is always visible; a placeholder is only an example.
- **Notice.** A sage box, ink text, 12px padding, 9px corners.
- **Disclaimer.** 11px muted text with a 3px mint rule on its left.
- **Chat.** Assistant bubble: mist ground, ink text, corners 14px 14px 14px 3px. Person
  bubble: forest ground, white text, corners 14px 14px 3px 14px. Chips are white pills with
  forest text.

## Logo

- Use `logo/gothos-owl-mark.png`. Never redraw, recolour, stretch, tilt or add effects.
- Header lockup: the mark at 33 by 40 pixels, then the words as live text in forest:
  GOTHOS (weight 700, letter-spacing .035em) and LABS (weight 300, .12em, 5px after).
- Light grounds only (bg, white, sage): the owl's face is see-through. On a dark ground or
  a photo, put it on a bg tile first.
- Clear space: the width of one owl eye. Smallest size: 15 pixels wide.

## The by-line

The small "by GOTHOS LABS" line shows who made a product, so each product can keep its own
logo. Tiny owl mark (15 by 18), "by" in muted, GOTHOS LABS in forest, 11px, linked to
https://www.gothoslabs.com. Always smaller than the product name. It belongs on the sign-in
screen, in the footer and on the About page.

## Mochi

The artwork is in the master design system. One Mochi per screen, where a guide helps (a
chat helper, a welcome, an empty screen). Never a logo or app icon, never in dense work
screens, never recoloured or cropped. Mochi's cream and orange are not interface colours.

## Motifs, icons and motion

- Leaf motif: a square with `border-radius: 90% 0 90% 0` in `leaf` at about 20% opacity,
  five at most on a screen, marketing pages only.
- Icons: line icons on a 24 by 24 grid, stroke about 1.6, round ends, no fill, in the
  colour of the text beside them. No emoji as icons. No stock photos.
- Motion is small and calm: rise 18px and fade in over 0.8s with
  `cubic-bezier(.2,.7,.2,1)`; hover changes 0.25s. Always respect `prefers-reduced-motion`.

## Access for everyone

- Focus is always visible: 3px solid `focus`, 5px offset (3px on fields).
- Every field has a visible label. Never use colour alone to say something.

## Not decided yet

- Error, warning and success colours. Until they are chosen, write the problem in plain
  words with an icon. Do not invent a brand red; keep whatever a product already uses.
- A dark theme.
- An icon set.

## Drawing a new product logo

A cousin of the owl, not a copy. Same greens (light near #6dcc86, mid near emerald, dark
near deep), a few smooth leaf-like curves with soft gradients, white gaps between shapes,
readable at 32 pixels. No owl in it. Product name beside it in Poppins 700, forest.
