' Cards of Factoria — silent launcher
' Opens the game in Microsoft Edge "app mode" (no tabs, no URL bar).
' Falls back to default browser if Edge is missing.

Option Explicit
Dim sh, url, edgePath
Set sh = CreateObject("WScript.Shell")
url = "https://cards-of-actoria.onrender.com"

On Error Resume Next
edgePath = sh.RegRead("HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe\")
If Err.Number <> 0 Or edgePath = "" Then
    Err.Clear
    edgePath = sh.RegRead("HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe\")
End If
On Error Goto 0

If edgePath <> "" Then
    sh.Run """" & edgePath & """ --app=" & url & " --window-size=1400,900 --new-window", 1, False
Else
    ' No Edge installed — open in default browser
    sh.Run url, 1, False
End If
