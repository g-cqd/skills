# Desktop, mobile, and local IPC

Use when the target is a desktop or mobile app, a privileged helper, an updater, a local daemon, a webview host, a
deep-link or file-type handler, a browser native-messaging host, or a local IPC client or server (Unix sockets, XPC,
Binder, D-Bus, named pipes). On Apple platforms, also apply `SKILL.md` §8.

## Discipline

- State the attacker's starting capability: another app, another OS user, a sandboxed child process, a downloaded
  document, a remote web origin, or a lower-privilege account. Harm within one account's own authority is not a
  boundary violation.
- Paths, process names, bundle or package ids, and sender fields in a message are not peer authentication. Use OS peer
  credentials, code-signing identity, capability handles, or protected channel state.
- A native bridge or helper authorizes each operation and the final resource after parsing. A trusted UI in front of
  it does not make its arguments trusted.
- OS sandboxes, signing, entitlements, permissions, keychain ACLs, exported-component policy, and consent prompts are
  real controls when they are visible and pinned. Packaging, signing, or merged manifests outside the repository make
  a candidate `needs_validation`.

## Classes

**Deep-link ambiguity.** Another app or page can invoke a route that changes state, imports data, completes
authentication, or selects an account without a current-session, one-time callback binding. Check URI normalization,
duplicate parameters, scheme and host matching, exported handlers, and replayed links.

**Account handoff confusion.** OAuth, SSO, magic-link, invite, pairing, or payment callbacks return to the wrong app,
profile, tenant, or pending transaction.

**File-open and intent authority.** An opened file, share intent, drag and drop, pasteboard item, notification
action, or open-file event triggers a privileged operation without checking content type, sender, current user
intent, and final target.

**Bridge reachable from the wrong origin.** Remote frames reach a JavaScript-to-native bridge meant for packaged
content. Check the origin at call time, after every navigation, redirect, subframe, popup, and error page.

**Over-broad bridge.** Web content can name arbitrary files, commands, IPC methods, credentials, or system actions
through a generic bridge.

**Webview file and universal access.** Remote content reads app files, custom schemes, or internal origins because
file access, universal access, mixed content, debugging, or custom protocol handlers join origins.

**IPC peer authentication.** A socket, pipe, XPC service, Binder or D-Bus interface, native-messaging host, or
loopback listener accepts a lower-trust peer without checking credentials, code identity, or sandbox token.

**Claimed principal versus channel.** The channel belongs to one app or user and a request field selects another user,
profile, or capability.

**Exported component overreach.** An exported activity, service, receiver, provider, or automation endpoint performs
an operation meant for the app itself. Read the final merged manifest.

**IPC correlation and lifecycle.** Predictable request ids, reused handles, stale channels, inherited descriptors, or
world-writable socket paths let one peer answer or cancel another's operation.

**Privileged helper as confused deputy.** A low-privilege caller selects a privileged command, file, service, user, or
setting without per-operation authorization; the helper must validate normalized arguments itself.

**Install, update, and repair paths.** A privileged installer reads manifests, scripts, symlinks, or repair state that
a lower-trust actor can write after authorization.

**Local file TOCTOU.** The app checks a path, then follows a replaced file, symlink, mount, or case change during a
privileged read or write. Use descriptor-relative operations.

**Local secret boundaries.** A keychain item, token file, backup, log, clipboard, notification preview, or config file
readable by another app, profile, or user with less authority. Plaintext readable only by the intended account is not
a finding.

**Logout and account-switch leakage.** Cached data, background tasks, widgets, notifications, webview storage, or
biometric approvals survive logout and appear under the next account.

**Pending-action confusion.** A notification, widget, shortcut, share sheet, biometric prompt, or deferred operation
authorizes a different action than it displays, runs after expiry, or uses another profile's state.

## Moves

- List every process, component, local endpoint, URL scheme, file association, webview origin, and helper, with its
  OS identity, privilege, callers, and callable operations.
- Read the final packaging inputs: merged manifest, entitlements, installer rules, native-messaging registration,
  protocol handlers, ACL creation.
- Validate with dummy profiles and local fixtures on an isolated machine or simulator; never touch other users' apps or
  credentials.

## Validation rules

1. Name the attacker's capability, the OS or app principal crossed, the entry channel, the accepted argument, and the
   unauthorized operation or disclosure.
2. Bridge findings cite both the origin control and the privileged native sink; IPC findings cite peer
   authentication and per-resource authorization; helper findings verify the final normalized destination.
3. Stop after showing the boundary result; no persistence and no broader system change.
