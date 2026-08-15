import os
import subprocess
import winreg

vbs_path = r"c:\Work\recorder\VoiceTyper.vbs"
work_dir = r"c:\Work\recorder"
wscript_exe = r"C:\Windows\System32\wscript.exe"
pythonw_exe = r"C:\Users\petrt\AppData\Local\hermes\hermes-agent\venv\Scripts\pythonw.exe"
main_py = r"c:\Work\recorder\main.py"

# 1. Записываем VoiceTyper.vbs со строгим скрытием окна (0 = SW_HIDE)
vbs_code = f'Set WshShell = CreateObject("WScript.Shell")\nWshShell.Run """{pythonw_exe}"" ""{main_py}""", 0, False\n'
with open(vbs_path, "w", encoding="utf-8") as f:
    f.write(vbs_code)

# 2. Список всех возможных путей к Рабочему столу
possible_desktops = [
    os.path.join(os.path.expanduser("~"), "Desktop"),
    os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop"),
    os.path.join(os.path.expanduser("~"), "OneDrive", "Рабочий стол"),
]

try:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as key:
        reg_desktop, _ = winreg.QueryValueEx(key, "Desktop")
        expanded_reg = os.path.expandvars(reg_desktop)
        if expanded_reg not in possible_desktops:
            possible_desktops.insert(0, expanded_reg)
except Exception:
    pass

startup_dir = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup")

# 3. Настраиваем ярлыки на запуск через wscript.exe (гарантированно 0 окон консоли)
for d in possible_desktops:
    if os.path.exists(d):
        lnk_path = os.path.join(d, "Voice Typer.lnk")
        ps_cmd = f'''
        $ws = New-Object -ComObject WScript.Shell;
        $s = $ws.CreateShortcut('{lnk_path}');
        $s.TargetPath = '{wscript_exe}';
        $s.Arguments = '"{vbs_path}"';
        $s.WorkingDirectory = '{work_dir}';
        $s.IconLocation = 'shell32.dll,168';
        $s.WindowStyle = 7;
        $s.Save();
        '''
        subprocess.run(["powershell", "-Command", ps_cmd], check=True)
        print(f"[OK] Скрытый ярлык настроен: {lnk_path}")

# Настраиваем автозагрузку
if os.path.exists(startup_dir):
    startup_lnk = os.path.join(startup_dir, "Voice Typer.lnk")
    ps_cmd = f'''
    $ws = New-Object -ComObject WScript.Shell;
    $s = $ws.CreateShortcut('{startup_lnk}');
    $s.TargetPath = '{wscript_exe}';
    $s.Arguments = '"{vbs_path}"';
    $s.WorkingDirectory = '{work_dir}';
    $s.IconLocation = 'shell32.dll,168';
    $s.WindowStyle = 7;
    $s.Save();
    '''
    subprocess.run(["powershell", "-Command", ps_cmd], check=True)
    print(f"[OK] Скрытый автозапуск настроен: {startup_lnk}")

print("\nВсе ярлыки перенастроены на 100% бесшумный запуск без окон.")
