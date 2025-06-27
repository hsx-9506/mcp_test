import tkinter as tk
from tkinter.scrolledtext import ScrolledText
import threading
import time
import json
import sys
import os

from agent_client import llm_agent

sys.path.append(os.path.dirname(__file__))

class MCPDemoUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MCP ↔ LLM 智能查詢介面")
        self.geometry("1280x820")
        self.minsize(950, 680)
        self.configure(bg="#f5f6fa")

        # 左側流程條
        self.left = tk.Frame(self, width=225, bg="#f5f6fa")
        self.left.pack(side=tk.LEFT, fill=tk.Y, padx=(16, 0), pady=18)
        self.steps = []
        self.step_labels = [
            "語意分析", "子問題拆解", "agent 發送 tool_call", "server 回傳 tool_result",
            "agent 處理/組裝", "LLM 回覆"
        ]
        for step in self.step_labels:
            lbl = tk.Label(self.left, text=f"🟢 {step}", font=("Microsoft JhengHei", 13, "bold"), anchor="w", pady=12, bg="#f5f6fa")
            lbl.pack(fill=tk.X, pady=1)
            self.steps.append(lbl)

        # 右側：上半部-分欄、下半部-console
        frm_right = tk.Frame(self, bg="#fafdff")
        frm_right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 頂部查詢區
        frm_top = tk.Frame(frm_right, bg="#f5f6fa")
        frm_top.pack(fill=tk.X, pady=(8,6), padx=16)
        tk.Label(frm_top, text="請輸入查詢需求：", font=("Microsoft JhengHei", 13), bg="#f5f6fa").pack(side=tk.LEFT)
        self.input_box = tk.Entry(frm_top, width=65, font=("Microsoft JhengHei", 13))
        self.input_box.pack(side=tk.LEFT, padx=4, expand=True, fill=tk.X)
        tk.Button(frm_top, text="送出查詢", font=("Microsoft JhengHei", 12, "bold"), bg="#4f8cff", fg="white", command=self.start_flow_thread).pack(side=tk.LEFT, padx=8)
        tk.Button(frm_top, text="清除紀錄", font=("Microsoft JhengHei", 11), command=self.clear_console, bg="#e0e0e0").pack(side=tk.LEFT)

        # 分欄顯示區
        frm_middle = tk.Frame(frm_right, bg="#e9f1fb")
        frm_middle.pack(fill=tk.X, padx=16, pady=(2, 0))
        self.left_box = tk.Text(frm_middle, width=45, height=10, font=("Microsoft JhengHei", 13), bg="#f8fcff", wrap=tk.WORD)
        self.right_box = tk.Text(frm_middle, width=55, height=10, font=("Microsoft JhengHei", 13), bg="#fff8fa", wrap=tk.WORD)
        self.left_box.pack(side=tk.LEFT, padx=(0,6), pady=3, fill=tk.BOTH, expand=True)
        self.right_box.pack(side=tk.LEFT, padx=(6,0), pady=3, fill=tk.BOTH, expand=True)
        self.left_box.insert(tk.END, "【語意分析】\n")
        self.right_box.insert(tk.END, "【子問題/Tool Call 拆解】\n")
        self.left_box.config(state=tk.DISABLED)
        self.right_box.config(state=tk.DISABLED)

        # 下方 log console（設只讀）
        self.console = ScrolledText(frm_right, font=("Consolas", 12), height=28, wrap=tk.WORD, bg="#fafdff", highlightthickness=0, bd=0)
        self.console.pack(fill=tk.BOTH, expand=True, padx=16, pady=(6,18))
        self.console.config(state=tk.DISABLED)

    def set_step(self, idx):
        for i, lbl in enumerate(self.steps):
            if i < idx:
                lbl.config(text=f"✅ {self.step_labels[i]}", fg="#2ecc71")
            elif i == idx:
                lbl.config(text=f"🔆 {self.step_labels[i]}", fg="#f39c12")
            else:
                lbl.config(text=f"🟢 {self.step_labels[i]}", fg="#b2bec3")

    def log(self, msg):
        self.console.config(state=tk.NORMAL)
        self.console.insert(tk.END, msg + "\n")
        self.console.see(tk.END)
        self.console.config(state=tk.DISABLED)

    def clear_console(self):
        self.console.config(state=tk.NORMAL)
        self.console.delete(1.0, tk.END)
        self.console.config(state=tk.DISABLED)
        self.left_box.config(state=tk.NORMAL)
        self.right_box.config(state=tk.NORMAL)
        self.left_box.delete(1.0, tk.END)
        self.right_box.delete(1.0, tk.END)
        self.left_box.insert(tk.END, "【語意分析】\n")
        self.right_box.insert(tk.END, "【子問題/Tool Call 拆解】\n")
        self.left_box.config(state=tk.DISABLED)
        self.right_box.config(state=tk.DISABLED)
        self.set_step(0)

    def start_flow_thread(self):
        threading.Thread(target=self.run_flow, daemon=True).start()

    def run_flow(self):
        user_q = self.input_box.get().strip()
        if not user_q:
            self.log("[請輸入查詢需求]")
            return
        try:
            # === 0. 語意分析 ===
            self.set_step(0)
            self.left_box.config(state=tk.NORMAL)
            self.left_box.delete(1.0, tk.END)
            self.left_box.insert(tk.END, "【語意分析】\n")
            self.left_box.config(state=tk.DISABLED)
            self.right_box.config(state=tk.NORMAL)
            self.right_box.delete(1.0, tk.END)
            self.right_box.insert(tk.END, "【子問題/Tool Call 拆解】\n")
            self.right_box.config(state=tk.DISABLED)
            self.log(f"[語意分析] 問題：{user_q}")

            decomp = llm_agent.decompose_query(user_q)
            intent = decomp.get("intent")
            reasoning = decomp.get("reasoning", "")
            keywords = decomp.get("keywords", [])
            self.left_box.config(state=tk.NORMAL)
            self.left_box.insert(tk.END, f"Intent: {intent}\n")
            if reasoning:
                self.left_box.insert(tk.END, f"Reasoning: {reasoning}\n")
            if keywords:
                self.left_box.insert(tk.END, f"關鍵字: {','.join(keywords)}\n")
            self.left_box.config(state=tk.DISABLED)
            time.sleep(0.3)

            # === 1. 子問題/Tool Call 拆解 ===
            self.set_step(1)
            self.right_box.config(state=tk.NORMAL)
            tool_calls = decomp.get("tool_calls") or decomp.get("subtasks") or []
            self.right_box.delete(1.0, tk.END)
            self.right_box.insert(tk.END, "【子問題/Tool Call 拆解】\n")
            if tool_calls:
                for i, sub in enumerate(tool_calls, 1):
                    if isinstance(sub, dict):
                        tool = sub.get("tool", "")
                        args = sub.get("args", {})
                        line = f"{i}. {tool}  參數: {json.dumps(args, ensure_ascii=False)}\n"
                        self.right_box.insert(tk.END, line)
                    else:
                        self.right_box.insert(tk.END, f"{i}. {sub}\n")
            else:
                self.right_box.insert(tk.END, "無法拆解子任務/Tool Call\n")
            self.right_box.config(state=tk.DISABLED)
            time.sleep(0.3)

            # ===== 2. agent 發送 tool_call =====
            self.set_step(2)
            self.log("[agent] 自動發送 tool_call...")
            tool_results = {}
            if tool_calls:
                for i, call in enumerate(tool_calls, 1):
                    if isinstance(call, dict):
                        tool = call.get("tool", "")
                        args = call.get("args", {}) or {}
                    else:
                        tool = str(call)
                        args = {}
                    self.log(f"[Tool Call {i}] 已發送（工具：{tool}，參數：{list(args.keys()) if args else '無'}) ...")
                    tool_result = llm_agent.call_server(tool, args)
                    tool_results[tool] = tool_result
                    self.set_step(3)
                    status = tool_result.get('status', 'UNKNOWN')
                    data = tool_result.get('data', [])
                    count = len(data) if isinstance(data, list) else (1 if data else 0)
                    self.log(f"[Server 回傳 {tool}] 狀態：{status}，資料筆數：{count}")
                    time.sleep(0.3)
            else:
                self.set_step(3)
                self.log("[server] 無 tool_call 可發送")

            # ===== 3. agent 處理/組裝 =====
            self.set_step(4)
            self.log("[agent] 處理/組裝摘要...")
            summary = []
            for tool, result in tool_results.items():
                summary_str = llm_agent.summarize_tool_result(tool, result)
                # ↓↓↓ 美化摘要多行縮排
                self.log(f"\n[摘要] {tool}：")
                for line in summary_str.splitlines():
                    if line.strip():
                        self.log(f"  {line}")
                    else:
                        self.log("")
                summary.append(summary_str)

            # ===== 4. LLM 回覆 =====
            self.set_step(5)
            self.log("\n[LLM 回覆]")
            reply = llm_agent.run_agent(user_q)
            for line in reply.splitlines():
                if line.strip():
                    self.log(f"  {line}")
                else:
                    self.log("")
            self.set_step(len(self.step_labels))
        except Exception as e:
            self.log(f"[錯誤] {e}")

if __name__ == "__main__":
    MCPDemoUI().mainloop()
