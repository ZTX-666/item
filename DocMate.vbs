Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
appDir = fso.GetParentFolderName(WScript.ScriptFullName)
electron = appDir & "\node_modules\electron\dist\electron.exe"
installBat = appDir & "\install-deps.bat"
If Not fso.FileExists(electron) Then
  shell.Run Chr(34) & installBat & Chr(34), 1, True
  If Not fso.FileExists(electron) Then
    MsgBox "Failed to install dependencies. Please run install-deps.bat or install Node.js LTS.", 48, "DocMate"
    WScript.Quit 1
  End If
End If
shell.CurrentDirectory = appDir
shell.Run Chr(34) & electron & Chr(34) & " " & Chr(34) & appDir & Chr(34), 1, False
