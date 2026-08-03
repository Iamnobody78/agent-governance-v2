; python.scm — 危险 Python 模式（S-expression 查询，零正则）
;
; 捕获名语义（由 ast_guard.py 声明表校验，见 EXPECTED_CAPTURES）:
;   @fn_exec  — 直接代码执行类（eval/exec/compile/动态导入/交互输入）
;   @fn_sys   — 系统访问类（命令执行/反序列化/动态库加载）
;   @imp_dyn  — 动态导入危险模块
;
; 模式 1: 直接代码执行函数（identifier 调用）
(call function: (identifier) @fn_exec
  (#match? @fn_exec "^(eval|exec|compile|__import__|input|globals|locals)$"))

; 模式 2: 危险模块方法调用（object.method 形态）
(call function: (attribute
    object: (identifier) @obj
    attribute: (identifier) @meth) @fn_sys
  (#match? @obj "^(os|subprocess|commands|pickle|yaml|shelve|ctypes|pty|telnetlib|ftplib|socket)$")
  (#match? @meth "^(system|popen|Popen|run|call|check_call|check_output|getoutput|getstatusoutput|loads|load|CDLL|WinDLL|open|spawn|sendall|connect)$"))

; 模式 3: 动态导入（importlib / __import__ 别名）
(call function: (attribute
    object: (identifier) @obj
    attribute: (identifier) @meth) @imp_dyn
  (#eq? @obj "importlib")
  (#any-of? @meth "import_module" "reload"))
