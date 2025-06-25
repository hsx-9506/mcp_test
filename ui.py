import tkinter as tk
from tkinter.scrolledtext import ScrolledText
import threading
import time
import json
import sys
import os
sys.path.append(os.path.dirname(__file__))
from agent_client import llm_agent

class MCPDemoUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MCP ↔ LLM 智能查詢介面")
        self.geometry("1100x750")
        self.minsize(800, 500)
        self.configure(bg="#f5f6fa")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # 左側流程條
        self.left = tk.Frame(self, width=260, bg="#f5f6fa", highlightthickness=0, bd=0)
        self.left.grid(row=0, column=0, sticky="ns", padx=(18,0), pady=18)
        self.left.grid_propagate(False)
        self.left.pack_propagate(False)
        self.steps = []
        self.step_labels = [
            "語意分析/子問題拆解", "agent 發送 tool_call", "server 回傳 tool_result",
            "agent 處理/組裝", "LLM 回覆"
        ]
        for step in self.step_labels:
            lbl = tk.Label(self.left, text=f"🟢 {step}", font=("Microsoft JhengHei", 14, "bold"), anchor="w", pady=16, bg="#f5f6fa")
            lbl.pack(fill=tk.X, pady=2)
            self.steps.append(lbl)

        # 右側：Console+對話框
        self.right = tk.Frame(self, bg="#f5f6fa")
        self.right.grid(row=0, column=1, sticky="nsew", padx=(10,18), pady=10)
        self.right.grid_rowconfigure(1, weight=1)
        self.right.grid_columnconfigure(0, weight=1)
        frm = tk.Frame(self.right, bg="#f5f6fa")
        frm.grid(row=0, column=0, sticky="ew", pady=6)
        frm.grid_columnconfigure(1, weight=1)
        tk.Label(frm, text="請輸入查詢需求：", font=("Microsoft JhengHei", 13), bg="#f5f6fa").grid(row=0, column=0, sticky="w")
        self.input_box = tk.Entry(frm, width=60, font=("Microsoft JhengHei", 13))
        self.input_box.grid(row=0, column=1, sticky="ew", padx=4)
        tk.Button(frm, text="送出查詢", font=("Microsoft JhengHei", 12, "bold"), bg="#4f8cff", fg="white", command=self.start_flow_thread).grid(row=0, column=2, padx=10)
        tk.Button(frm, text="清除紀錄", font=("Microsoft JhengHei", 11), command=self.clear_console, bg="#e0e0e0").grid(row=0, column=3)

        # Console顯示區
        self.console = ScrolledText(self.right, font=("Consolas", 12), height=38, wrap=tk.WORD, bg="#fafdff", highlightthickness=0, bd=0)
        self.console.grid(row=1, column=0, sticky="nsew", pady=6)

        self.update_idletasks()
        self.after(100, self.fix_layout)

    def fix_layout(self):
        # 強制左側寬度固定，避免因自動調整導致抖動
        self.left.config(width=260)
        self.left.update_idletasks()
        self.right.update_idletasks()
        self.update_idletasks()

    def set_step(self, idx, status="on"):
        for i, lbl in enumerate(self.steps):
            if i < idx:
                lbl.config(text=f"✅ {lbl.cget('text')[2:]}", fg="#2ecc71")
            elif i == idx:
                lbl.config(text=f"🔆 {lbl.cget('text')[2:]}", fg="#f39c12")
            else:
                lbl.config(text=f"🟢 {lbl.cget('text')[2:]}", fg="#b2bec3")

    def log(self, msg):
        self.console.insert(tk.END, msg + "\n")
        self.console.see(tk.END)

    def clear_console(self):
        self.console.delete(1.0, tk.END)

    def start_flow_thread(self):
        threading.Thread(target=self.run_flow, daemon=True).start()

    def run_flow(self):
        user_q = self.input_box.get().strip()
        if not user_q:
            self.log("[請輸入查詢需求]")
            return
        self.set_step(0)
        self.log(f"[語意分析] 問題：{user_q}")
        time.sleep(0.3)
        try:
            # 語意分析與子問題拆解
            decomp = llm_agent.decompose_query(user_q)
            intent = decomp.get("intent")
            subtasks = decomp.get("subtasks") or decomp.get("tool_calls")
            self.log(f"[語意分析] intent: {intent}")
            self.log("[子問題/Tool Call 拆解]：")
            if subtasks:
                for i, sub in enumerate(subtasks, 1):
                    self.log(f"  {i}. {sub}")
            else:
                self.log("  無法拆解子任務/Tool Call")
            # ===== 2. agent 發送 tool_call =====
            self.set_step(1)
            self.log("[agent] 自動發送 tool_call...")
            tool_results = {}
            if subtasks:
                for i, call in enumerate(subtasks, 1):
                    tool = call["tool"] if isinstance(call, dict) and "tool" in call else str(call)
                    args = call.get("args", {}) if isinstance(call, dict) else {}
                    self.log(f"[Tool Call {i}] 已發送（工具：{tool}，參數：{list(args.keys()) if args else '無'}) ...")
                    tool_result = llm_agent.call_server(tool, args)
                    tool_results[tool] = tool_result
                    self.set_step(2)
                    # 只顯示回傳狀態與資料筆數，不顯示全部內容
                    status = tool_result.get('status', 'UNKNOWN')
                    data = tool_result.get('data', [])
                    count = len(data) if isinstance(data, list) else (1 if data else 0)
                    self.log(f"[Server 回傳 {tool}] 狀態：{status}，資料筆數：{count}")
                    time.sleep(0.3)
            else:
                self.set_step(2)
                self.log("[server] 無 tool_call 可發送")
            # ===== 3. agent 處理/組裝 =====
            self.set_step(3)
            self.log("[agent] 處理/組裝摘要...")
            summary = []
            for tool, result in tool_results.items():
                summary_str = llm_agent.summarize_tool_result(tool, result)
                # 只顯示前50字，避免太長
                short_summary = summary_str[:50].replace('\n', ' ') + ("..." if len(summary_str) > 50 else "")
                self.log(f"[摘要] {tool}：{short_summary}")
                summary.append(summary_str)
            # ===== 4. LLM 回覆 =====
            self.set_step(4)
            self.log("[LLM] 統整回覆中...")
            reply = llm_agent.run_agent(user_q)
            self.log(f"[LLM 回覆] {reply}")
        except Exception as e:
            self.log(f"[錯誤] {e}")

if __name__ == "__main__":
    MCPDemoUI().mainloop()
