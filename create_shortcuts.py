import os
import sys

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

pythonw_path = r"C:\Users\petrt\AppData\Local\hermes\hermes-agent\venv\Scripts\pythonw.exe"
main_script = r"c:\Work\recorder\main.py"
desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
shortcut_path = os.path.join(desktop_dir, "Voice Typer.lnk")
startup_dir = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup")
startup_shortcut_path = os.path.join(startup_dir, "Voice Typer.lnk")

# 1. Создаем VBS скрипт для фонового запуска
vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.Run """{pythonw_path}"" ""{main_script}""", 0, False
'''
vbs_path = r"c:\Work\recorder\VoiceTyper.vbs"
with open(vbs_path, "w", encoding="utf-8") as f:
    f.write(vbs_content)
print(f"Создан VBS лаунчер: {vbs_path}")

# 2. Создаем ярлык на Рабочем столе через WScript.Shell
import subprocess
ps_cmd = f'''
$ws = New-Object -ComObject WScript.Shell;
$s = $ws.CreateShortcut('{shortcut_path}');
$s.TargetPath = '{pythonw_path}';
$s.Arguments = '"{main_script}"';
$s.WorkingDirectory = 'c:\\Work\\recorder';
$s.IconLocation = 'shell32.dll,168';
$s.Save();

$s2 = $ws.CreateShortcut('{startup_shortcut_path}');
$s2.TargetPath = '{pythonw_path}';
$s2.Arguments = '"{main_script}"';
$s2.WorkingDirectory = 'c:\\Work\\recorder';
$s2.IconLocation = 'shell32.dll,168';
$s2.Save();
'''
subprocess.run(["powershell", "-Command", ps_cmd], check=True)
print(f"[OK] Создан ярлык на Рабочем столе: {shortcut_path}")
print(f"[OK] Добавлен в автозагрузку Windows: {startup_shortcut_path}")
print("\nVoice Typer готов и будет запускаться автоматически при включении Windows.")
