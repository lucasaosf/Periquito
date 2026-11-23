Set WshShell = CreateObject("WScript.Shell")
strPath = WshShell.CurrentDirectory
WshShell.Run chr(34) & strPath & "\Iniciar_App_Desktop.bat" & chr(34), 0
Set WshShell = Nothing
