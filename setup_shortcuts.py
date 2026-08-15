import os
import subprocess
import sys

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def get_pythonw_path() -> str:
    """Dynamically finds the pythonw.exe corresponding to current Python environment."""
    current_python = sys.executable
    if "pythonw.exe" in current_python.lower():
        return current_python
    pythonw = os.path.join(os.path.dirname(current_python), "pythonw.exe")
    if os.path.exists(pythonw):
        return pythonw
    return current_python


def setup_shortcuts():
    """Generates VBS launcher, Desktop shortcut, and Windows Startup shortcut."""
    base_dir = os.path.abspath(os.path.dirname(__file__))
    main_script = os.path.join(base_dir, "main.py")
    pythonw_path = get_pythonw_path()

    desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
    shortcut_path = os.path.join(desktop_dir, "Voice Typer.lnk")

    startup_dir = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup")
    startup_shortcut_path = os.path.join(startup_dir, "Voice Typer.lnk")

    # 1. Create VoiceTyper.vbs (silent background launcher without console window)
    vbs_path = os.path.join(base_dir, "VoiceTyper.vbs")
    vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "{base_dir}"
WshShell.Run """{pythonw_path}"" ""{main_script}""", 0, False
'''
    with open(vbs_path, "w", encoding="utf-8") as f:
        f.write(vbs_content)
    print(f"[OK] Generated VBS launcher: {vbs_path}")

    # 2. Create Desktop & Startup shortcuts via PowerShell WScript.Shell COM object
    ps_cmd = f'''
$ws = New-Object -ComObject WScript.Shell;
$s = $ws.CreateShortcut('{shortcut_path}');
$s.TargetPath = 'wscript.exe';
$s.Arguments = '"{vbs_path}"';
$s.WorkingDirectory = '{base_dir}';
$s.IconLocation = 'shell32.dll,168';
$s.Save();

$s2 = $ws.CreateShortcut('{startup_shortcut_path}');
$s2.TargetPath = 'wscript.exe';
$s2.Arguments = '"{vbs_path}"';
$s2.WorkingDirectory = '{base_dir}';
$s2.IconLocation = 'shell32.dll,168';
$s2.Save();
'''
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=True)
        print(f"[OK] Desktop shortcut created: {shortcut_path}")
        print(f"[OK] Windows Startup shortcut created: {startup_shortcut_path}")
        print("\nVoice Typer is configured to run silently in the background!")
    except Exception as e:
        print(f"[ERROR] Failed to create shortcuts: {e}")


if __name__ == "__main__":
    setup_shortcuts()
