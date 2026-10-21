# Run and profile commands

Detail for `SKILL.md` §2. Read it when installing, launching, or profiling an app from the command line.

```bash
xcrun simctl boot "<device>"
xcrun simctl install booted <App.app>
xcrun simctl launch booted <bundle-id>
xcrun devicectl device install app --device <id> <App.app>   # physical device
xcrun xctrace record --template 'Time Profiler' --launch <App.app>
```
