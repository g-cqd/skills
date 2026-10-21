# On-device interaction detail

Detail for `SKILL.md` §6. Read the section a step names when you reach it.

## Contents

- [Interaction syntax](#interaction-syntax)
- [tvOS](#tvos)
- [Run arguments](#run-arguments)
- [Hierarchy dump format](#hierarchy-dump-format)
- [Overlapping apps](#overlapping-apps)
- [Timing and retries](#timing-and-retries)
- [Judging what you see](#judging-what-you-see)

---

## Interaction syntax

| Command | Meaning |
|---|---|
| `t <x> <y> [duration]` | Tap, optional hold |
| `d <x> <y>` | Double tap |
| `t <x1> <y1> f <x2> <y2> [duration]` | Swipe |
| `b h/p/u/d [duration]` | Hardware button: Home, Power, VolUp, VolDown |
| `drag <x1> <y1> <x2> <y2> [hold] [move]` | Press-and-hold, then move slowly: list reordering, drag-and-drop |
| `mt [x y, ...] dur [x y, ...] dur ...` | Multi-touch keyframes (each `[...]` lists the touches, the number after it is the travel time to the next keyframe, the last one the hold before lifting). `"mt [100 300, 300 300] 0.5 [175 300, 225 300] 0.5"` is a two-finger pinch |
| `sender keyboard kbd <text>` | Type text — **must be last in the chain**; everything after `kbd ` is verbatim, multiple spaces preserved |
| `w <duration>` | Wait |
| `orientation <value>` | iOS only: `faceDown`, `faceUp`, `landscapeLeft`, `landscapeRight`, `portrait`, `portraitUpsideDown` |
| `b c/s/a [duration]`, `c <turns>` | watchOS only: Digital Crown press, side button, Action button (some devices); rotate the crown (1.0 is one revolution, the sign sets direction) |
| `r up/down/left/right/select/menu/playpause/home` | tvOS only: Siri Remote |

```
"t 200 600 f 200 200 0.3"          swipe up (scroll down the content)
"b h b h"                          home twice → app switcher
"b h w 0 b h"                      wake and unlock (no-passcode devices)
"sender keyboard kbd submit\u{000A}"   type, then Return
```

Special characters use `\u{XXXX}`: `\u{000A}` return, `\u{0009}` tab.

---

## tvOS

tvOS is focus-based: coordinate taps do not apply, and only the focused element can be activated.
Read the hierarchy for the focusable elements and the one marked `Focused`, move with `r up/down/left/right`,
activate with `r select`, go back with `r menu`. Chain the presses in one command and capture
once: `r right r right r right`, then capture to confirm where focus landed.

---

## Run arguments

`DeviceInteractionInstallAndRun` takes optional `commandLineArguments` and `environmentVariables`.
Use `$(inherited)` to preserve the scheme's existing values —
`["$(inherited)", "--reset-state"]`, or `{"$(inherited)": "", "DEBUG_MODE": "1"}`.
**Prefer these over editing the scheme**: they apply to one run and leave the user's configuration
untouched.

---

## Hierarchy dump format

Hierarchy dumps carry a calculated `hitPoint` per element:

```
UIView {{100, 200}, {60, 30}}, hitPoint: {130.0, 215.0}
  UIButton "Login" {{110, 205}, {30, 20}}, hitPoint: {125.0, 215.0}
```

`{100, 200}` is the origin, `{60, 30}` the size, `hitPoint:` the best point to tap.

---

## Overlapping apps

When windows from more than one app overlap, each element line carries
`activationBundleId: <id>`. Interacting with such an element needs `activationBundleId` passed to
`DeviceEventSynthesize` first (it may be passed with no command). Activation is expensive, so pass
it only for those elements.

---

## Timing and retries

- **After launch**, the app may take seconds. Capture and confirm the hierarchy holds meaningful
  UI before interacting; a launch screen or empty tree means capture again.
- **After an interaction that did nothing**, recapture and retry **once** — the element may have
  moved mid-animation. If it fails again, report it rather than looping.
- **Wait for a loading element to settle before interacting.** A tap on a spinner lands on
  whatever replaces it.
- Runtime logs help; if a timing bug is suspected, suggest to the main agent that temporary `print`
  statements would isolate it.

---

## Judging what you see

| Category | Action |
|---|---|
| **Functional bug** — no response to tap, wrong navigation, crash, missing or empty data | **Report** |
| **Visual bug** — overlapping or truncated text, off-screen elements, wrong colors, broken alignment | **Report** |
| **Unexpected exit** — crash or termination; track the pid and capture stdout | **Report** |
| **Transient state** — spinners, animations, keyboard transitions | Do not report; recapture after it settles |
| **Expected behavior** — empty-state placeholders, disabled buttons on incomplete forms, permission dialogs | Do not report |
