import os
import subprocess
import sys

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def get_pythonw_path() -> str:
    """Finds the primary pythonw.exe that contains all installed dependencies."""
    candidates = [
        r"C:\Users\petrt\AppData\Local\Programs\Python\Python313\pythonw.exe",
        os.path.join(os.path.dirname(sys.executable), "pythonw.exe"),
        sys.executable.replace("python.exe", "pythonw.exe")
    ]
    for cand in candidates:
        if os.path.exists(cand):
            return cand
    return sys.executable


def setup_shortcuts():
    """Generates VBS launcher, Desktop shortcut, and Windows Startup shortcut."""
    base_dir = os.path.abspath(os.path.dirname(__file__))
    main_script = os.path.join(base_dir, "main.py")
    pythonw_path = get_pythonw_path()

    # 1. Update VoiceTyper.vbs
    vbs_path = os.path.join(base_dir, "VoiceTyper.vbs")
    vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "{base_dir}"
WshShell.Run """{pythonw_path}"" ""{main_script}""", 0, False
'''
    with open(vbs_path, "w", encoding="utf-8") as f:
        f.write(vbs_content)
    print(f"[OK] Generated VBS launcher: {vbs_path}")

    # 2. Update VoiceTyper.bat
    bat_path = os.path.join(base_dir, "VoiceTyper.bat")
    bat_content = f'''@echo off
cd /d "%~dp0"
start "" "{pythonw_path}" main.py
'''
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat_content)
    print(f"[OK] Generated BAT launcher: {bat_path}")

    # 3. Create Desktop & Startup shortcuts via PowerShell
    ps_cmd = f'''
$pythonw = "{pythonw_path}";
$mainScript = "{main_script}";
$workDir = "{base_dir}";
$ws = New-Object -ComObject WScript.Shell;

$desktopDirs = @(
    [System.Environment]::GetFolderPath('Desktop'),
    [System.IO.Path]::Combine($env:USERPROFILE, 'Desktop'),
    [System.IO.Path]::Combine($env:USERPROFILE, 'OneDrive', 'Desktop'),
    [System.IO.Path]::Combine($env:USERPROFILE, 'OneDrive', 'Рабочий стол')
);

foreach ($d in $desktopDirs) {{
    if (Test-Path $d) {{
        $s = $ws.CreateShortcut([System.IO.Path]::Combine($d, 'Voice Typer.lnk'));
        $s.TargetPath = $pythonw;
        $s.Arguments = "`"$mainScript`"";
        $s.WorkingDirectory = $workDir;
        $s.IconLocation = "shell32.dll,168";
        $s.Description = "VoiceTyper AI Voice Typing";
        $s.Save();
        Write-Host "[OK] Desktop shortcut created in: $d";
    }}
}}

$startupDir = [System.Environment]::GetFolderPath('Startup');
if (Test-Path $startupDir) {{
    $s2 = $ws.CreateShortcut([System.IO.Path]::Combine($startupDir, 'Voice Typer.lnk'));
    $s2.TargetPath = $pythonw;
    $s2.Arguments = "`"$mainScript`"";
    $s2.WorkingDirectory = $workDir;
    $s2.IconLocation = "shell32.dll,168";
    $s2.Description = "VoiceTyper AI Voice Typing";
    $s2.Save();
    Write-Host "[OK] Startup shortcut created: $([System.IO.Path]::Combine($startupDir, 'Voice Typer.lnk'))";
}}
'''
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=True)
        print("\nVoice Typer shortcuts successfully configured!")
    except Exception as e:
        print(f"[ERROR] Failed to create shortcuts: {e}")


if __name__ == "__main__":
    setup_shortcuts()
