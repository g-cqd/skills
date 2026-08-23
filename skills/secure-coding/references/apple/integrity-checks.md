# Integrity Checks

**Note**: These checks raise the bar but are NOT security boundaries. A determined attacker will bypass them.

## Jailbreak Detection

```swift
import MachO

enum IntegrityCheck {
  /// Check for common jailbreak artifacts (easily bypassed)
  static func checkFilesystem() -> Bool {
    let suspiciousPaths = [
      "/Applications/Cydia.app",
      "/private/var/lib/apt",
      "/usr/sbin/sshd",
      "/usr/bin/ssh",
      "/bin/bash",
      "/usr/libexec/sftp-server"
    ]
    return !suspiciousPaths.contains { FileManager.default.fileExists(atPath: $0) }
  }
}
```

## Dylib Injection Detection

```swift
/// Check for injected libraries
static func checkDylibs() -> Bool {
  let suspiciousLibs = ["substrate", "substitute", "frida", "cycript", "ssl_kill"]

  for i in 0..<_dyld_image_count() {
    guard let name = _dyld_get_image_name(i) else { continue }
    let path = String(cString: name).lowercased()

    if suspiciousLibs.contains(where: { path.contains($0) }) {
      return false
    }
  }
  return true
}
```

## Debugger Detection

```swift
/// Check if debugger attached
static func checkDebugger() -> Bool {
  var info = kinfo_proc()
  var size = MemoryLayout<kinfo_proc>.stride
  var mib: [Int32] = [CTL_KERN, KERN_PROC, KERN_PROC_PID, getpid()]

  let result = sysctl(&mib, UInt32(mib.count), &info, &size, nil, 0)
  guard result == 0 else { return true }

  return (info.kp_proc.p_flag & P_TRACED) == 0
}
```

## Appropriate Responses

When integrity checks fail, consider:
- Degrading functionality (disable sensitive features)
- Logging the event (for analytics, not blocking)
- Refusing to store new secrets
- Informing the user of reduced security

Never rely solely on these checks for security — they are defense-in-depth measures.
