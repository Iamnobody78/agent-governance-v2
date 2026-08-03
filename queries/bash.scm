; bash.scm — 危险 Shell 命令模式（S-expression 查询，零正则）
;
; 捕获名语义:
;   @cmd_danger — 破坏性/越权命令（rm/sudo/格式化/网络下载执行/提权/服务控制）
;   @flag_danger — 危险标志组合（rm -rf /、dd if=/dev/zero 等）
;
; 注意: tree-sitter 0.21.3 未实现 #any-of? 谓词（编译接受但运行时忽略），
; 故值表统一用 #match? 正则表达（正则仅作模式筛选, AST 解析仍在 tree-sitter）。
;
; 危险命令表（全部声明于此，ast_guard.py 零命令名硬编码 — P3 验收约束）
(command name: (command_name) @cmd_danger
  (#match? @cmd_danger
    "^(rm|shred|mkfs|dd|fdisk|parted|gdisk|sfdisk|format|sudo|su|passwd|chmod|chown|chattr|usermod|useradd|deluser|curl|wget|nc|ncat|telnet|ssh|scp|rsync|socat|kill|pkill|killall|reboot|shutdown|halt|poweroff|init|systemctl|iptables|ufw|nft|docker|kubectl|helm|kubeadm|mysql|psql|sqlite3|mongo|redis-cli|crontab|at|nohup|setsid|daemon|service|python|python3|perl|ruby|php|node|java|scala|groovy|powershell|pwsh|cmd|bash|sh|zsh|ksh)$"))

; 危险标志组合: rm -rf / 等（name: (word) 匹配标志）
(command
  name: (command_name) @cmd_danger
  (#match? @cmd_danger "^(rm|dd|mkfs|chmod|chown|shred)$")
  .
  argument: (word) @flag_danger
  (#match? @flag_danger "^(/|-rf|--recursive|--force|if=/dev/zero|of=/dev/sd)"))
