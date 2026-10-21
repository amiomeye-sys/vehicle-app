Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "python app.py", 0, False
WshShell.Run "ngrok http 5000", 0, False
Set WshShell = Nothing