Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
agent = fso.GetParentFolderName(WScript.ScriptFullName) & "\GHMCPrintAgent.exe"
shell.Run Chr(34) & agent & Chr(34), 0, False
