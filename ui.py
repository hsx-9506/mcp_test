import tkinter as tk
from tkinter import ttk
import threading
import time
import agent_client.llm_agent as llm_agent

# ----------- 圓角聊天氣泡 -------------
class BubbleCanvas(tk.Canvas):
    def __init__(self, parent, text, sender="assistant", **kwargs):
        bg = "#dbeafe" if sender == "user" else "#ececec"
        fg = "#185abd" if sender == "user" else "#333"
        font = ("Microsoft JhengHei", 13)
        padding = 22
        radius = 16
        # 先初始化最小尺寸
        super().__init__(parent, bg="#fafdff", highlightthickness=0, bd=0, width=480, height=40)
        text_id = self.create_text(padding, padding//2, text=text, font=font, anchor="nw", fill=fg, width=430)
        self.update_idletasks()
        bbox = self.bbox(text_id)
        if bbox:
            w = bbox[2] - bbox[0] + padding * 2
            h = bbox[3] - bbox[1] + padding
            # 先清空，畫圓角框（在最下層）
            self.delete("bg")
            self.create_round_rect(0, 0, w, h, r=radius, fill=bg, outline=bg, tags="bg")
            self.tag_lower("bg")
            self.config(width=w, height=h)
        self.after(10, self.fit_canvas)
    def fit_canvas(self):
        self.update_idletasks()
        bbox = self.bbox("all")
        if bbox:
            w = max(bbox[2] - bbox[0] + 8, 80)
            h = max(bbox[3] - bbox[1] + 8, 40)
            self.config(width=w, height=h)
    def create_round_rect(self, x1, y1, x2, y2, r=18, **kwargs):
        points = [
            x1+r, y1, x2-r, y1, x2, y1, x2, y1+r,
            x2, y2-r, x2, y2, x2-r, y2, x1+r, y2,
            x1, y2, x1, y2-r, x1, y1+r, x1, y1
        ]
        return self.create_polygon(points, smooth=True, **kwargs)

# ----------- 複製按鈕圖示小元件（用Canvas畫兩個重疊方框）-------------
class CopyIcon(tk.Canvas):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, width=22, height=22, bg="#fafdff", highlightthickness=0, bd=0)
        self.create_rectangle(6, 10, 18, 20, outline="#888", width=2, fill="#fafdff")
        self.create_rectangle(2, 4, 14, 16, outline="#333", width=2, fill="#fafdff")

# ----------- 主 UI -------------
class MCPChatUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MCP智慧產線 AI 助手")
        self.geometry("1200x780")
        self.configure(bg="#f6f8fb")
        self.session_history = []
        self.summary_records = []
        self.step_outputs = [""] * 6  # 每個步驟詳細輸出
        self.summary_text = ""        # 摘要內容
        self.step_panel_visible = False

        # ===== 左側步驟燈+按鈕(垂直區塊) =====
        self.left = tk.Frame(self, width=180, bg="#f5f6fa")
        self.left.pack(side=tk.LEFT, fill=tk.Y, padx=(0,0), pady=0)
        self.left.pack_propagate(False)
        self.step_labels = []
        self.step_names = [
            "語意分析", "子問題拆解", "agent tool_call",
            "server回傳", "組裝摘要", "LLM回覆"
        ]
        for step in self.step_names:
            lbl = tk.Label(self.left, text=f"🟢 {step}", font=("Microsoft JhengHei", 13, "bold"),
                           anchor="w", pady=13, bg="#f5f6fa")
            lbl.pack(fill=tk.X, pady=0)
            self.step_labels.append(lbl)
        # ===== 步驟內容顯示/收合按鈕(左下) =====
        self.list_btn = tk.Button(self.left, text="☰", font=("Arial", 20), bg="#f5f6fa", bd=0, 
                                  activebackground="white", command=self.toggle_step_panel)
        self.list_btn.pack(side=tk.BOTTOM, anchor="sw", pady=15, padx=10)
        # 新增清除紀錄按鈕
        self.clear_btn = tk.Button(self.left, text="清除紀錄", font=("Microsoft JhengHei", 12, "bold"), bg="#4f8cff", fg="white", bd=0, activebackground="#fff0f0", command=self.clear_history)
        self.clear_btn.pack(side=tk.BOTTOM, anchor="sw", pady=(0,8), padx=10)

        # ===== 主內容框架 =====
        self.main_area = tk.Frame(self, bg="#fafdff")
        self.main_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.main_area.grid_rowconfigure(0, weight=1)
        self.main_area.grid_columnconfigure(0, weight=1)

        # ===== 聊天區塊（含可滾動canvas+bubble）=====
        self.chat_frame = tk.Frame(self.main_area, bg="#fafdff")
        self.chat_frame.grid(row=0, column=0, sticky="nsew")
        self.chat_canvas = tk.Canvas(self.chat_frame, bg="#fafdff", highlightthickness=0, bd=0)
        self.chat_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar = tk.Scrollbar(self.chat_frame, orient="vertical", command=self.chat_canvas.yview)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_canvas.configure(yscrollcommand=self.scrollbar.set)
        self.bubble_frame = tk.Frame(self.chat_canvas, bg="#fafdff")
        self.bubble_window = self.chat_canvas.create_window((0,0), window=self.bubble_frame, anchor="nw", width=10)
        def on_resize(event):
            self.chat_canvas.itemconfig(self.bubble_window, width=event.width)
        self.chat_canvas.bind("<Configure>", on_resize)
        self.bubble_frame.bind("<Configure>", lambda e: self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all")))
        self.chat_canvas.bind_all("<MouseWheel>", self._on_mousewheel)  # Windows
        self.chat_canvas.bind_all("<Button-4>", self._on_mousewheel)    # Linux 上滾
        self.chat_canvas.bind_all("<Button-5>", self._on_mousewheel)    # Linux 下滾
        self.chat_canvas.bind_all("<Shift-MouseWheel>", self._on_mousewheel)  # 橫向

        # ===== 輸入區（永遠在聊天區正下方）=====
        self.input_bg = tk.Frame(self.main_area, bg="#ededed")  # 淺灰色
        self.input_bg.grid(row=1, column=0, sticky="ew")
        self.input_area = tk.Frame(self.input_bg, bg="#ededed")  # 淺灰色
        self.input_area.pack(padx=24, pady=11, fill=tk.X)
        self.input_box = tk.Entry(self.input_area, font=("Microsoft JhengHei", 13), relief="flat", bg="#fafdff",
                                  highlightbackground="#c9d6ef", highlightcolor="#6ca6fc", highlightthickness=2)
        self.input_box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10), ipady=8, ipadx=6)
        self.input_box.bind("<Return>", self.on_send)
        send_btn = tk.Button(self.input_area, text="送出", font=("Microsoft JhengHei", 12, "bold"),
                  bg="#4f8cff", fg="white", relief="flat", borderwidth=0, padx=20, pady=8, command=self.on_send)
        send_btn.pack(side=tk.LEFT, ipady=2)

        # ===== 步驟輸出/摘要區（預設隱藏，展開在步驟燈右邊） =====
        self.step_panel = tk.Frame(self, bg="#f5f9ff", width=380)
        self.step_panel.pack_propagate(False)
        self._panel_title = tk.Label(
            self.step_panel,
            text="步驟執行內容 / 摘要結果",
            font=("Microsoft JhengHei", 15, "bold"),
            bg="#e4f3ff"
        )
        self._panel_title.pack(fill=tk.X, padx=0, pady=(6,3))
        self.step_panel_widgets = []

        # ==== 初始提示 ====
        self.add_bubble("請在下方輸入您的查詢需求。", sender="assistant")

    # ========== 步驟/摘要內容長條側欄 顯示/收合 ==========
    def toggle_step_panel(self):
        if not self.step_panel_visible:
            self.step_panel_visible = True
            self.step_panel.place(x=180, y=0, relheight=1, width=400)
            self.update_step_panel()
        else:
            self.step_panel.place_forget()
            self.step_panel_visible = False

    def update_step_panel(self):
        for w in self.step_panel_widgets:
            w.destroy()
        self.step_panel_widgets.clear()
        for i, step in enumerate(self.step_names[:-1]):
            frame = tk.LabelFrame(
                self.step_panel,
                text=step,
                font=("Microsoft JhengHei", 11, "bold"),
                bg="#fafdff", fg="#1e2835", relief="ridge", bd=2
            )
            frame.pack(fill=tk.X, padx=13, pady=(6,2))
            box = tk.Text(frame, font=("Consolas", 11), bg="#fff", height=3, wrap=tk.WORD)
            box.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            box.insert(tk.END, self.step_outputs[i] if self.step_outputs[i] else "(無內容)")
            box.config(state=tk.DISABLED, height=4)
            self.step_panel_widgets.append(frame)
        frame = tk.LabelFrame(self.step_panel, text="摘要/工具結果", font=("Microsoft JhengHei", 11, "bold"),
                              bg="#fafdff", fg="#1e2835", relief="ridge", bd=2)
        frame.pack(fill=tk.BOTH, expand=True, padx=13, pady=(6,8))
        box = tk.Text(frame, font=("Consolas", 11), bg="#fff", height=8, wrap=tk.WORD)
        box.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        box.insert(tk.END, self.summary_text if self.summary_text else "(無內容)")
        box.config(state=tk.DISABLED)

    # ========== 聊天功能 ==========
    def add_bubble(self, text, sender="assistant"):
        bubble_row = tk.Frame(self.bubble_frame, bg="#fafdff")
        bubble_row.pack(anchor="e" if sender=="user" else "w", pady=7, padx=6, fill=tk.NONE)
        # bubble_row.pack_propagate(False)  # 讓內容自動撐開
        bubble = BubbleCanvas(bubble_row, text, sender=sender)
        bubble.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        if sender == "assistant":
            icon = CopyIcon(bubble_row)
            icon.pack(side=tk.LEFT, anchor="sw", pady=(6,4), padx=(8,0))
            icon.bind("<Button-1>", lambda e, t=text: self.copy_to_clipboard(t))
            icon.bind("<Enter>", lambda e: self._set_tooltip_widget(icon) or self.show_tooltip(icon, "複製"))
            icon.bind("<Leave>", lambda e: self.hide_tooltip())
        self.update_idletasks()
        self.chat_canvas.yview_moveto(1.0)


    def _set_tooltip_widget(self, widget):
        self._current_tooltip_widget = widget
        return None

    def copy_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        # 顯示提示
        if hasattr(self, "_current_tooltip_widget") and self._current_tooltip_widget:
            self.show_tooltip(self._current_tooltip_widget, "複製成功！", temp=800)

    # --- tooltip小工具（內嵌氣泡下方）---
    def show_tooltip(self, widget, text, temp=None):
        self.hide_tooltip()
        x = widget.winfo_rootx() - widget.master.winfo_rootx()
        y = widget.winfo_rooty() - widget.master.winfo_rooty() + widget.winfo_height() + 3
        tooltip = tk.Label(widget.master, text=text, font=("Microsoft JhengHei", 10),
                           bg="black", fg="white", padx=8, pady=3, bd=0, relief="solid")
        tooltip.place(x=x, y=y)
        self._tooltip = tooltip
        self._current_tooltip_widget = widget
        if temp:
            self.after(temp, self.hide_tooltip)

    def hide_tooltip(self):
        if hasattr(self, "_tooltip") and self._tooltip:
            self._tooltip.destroy()
            self._tooltip = None
        self._current_tooltip_widget = None

    # ========== 步驟進度/內容 ==========
    def set_step(self, idx, step_output=None):
        for i, lbl in enumerate(self.step_labels):
            if i < idx:
                lbl.config(text=f"✅ {self.step_names[i]}", fg="#2ecc71")
            elif i == idx:
                if i == len(self.step_names) - 1:
                    lbl.config(text=f"✅ {self.step_names[i]}", fg="#2ecc71")
                else:
                    lbl.config(text=f"🟡 {self.step_names[i]}", fg="#f39c12")
            else:
                lbl.config(text=f"🟢 {self.step_names[i]}", fg="#185abd")
        if step_output is not None and idx < len(self.step_outputs):
            self.step_outputs[idx] = step_output
        if self.step_panel_visible:
            self.update_step_panel()


    def update_summary(self, summary):
        self.summary_text = summary
        if self.step_panel_visible:
            self.update_step_panel()

    # ========== LLM訊息/流程 ==========
    def on_send(self, event=None):
        user_q = self.input_box.get().strip()
        if not user_q:
            return
        self.add_bubble(user_q, sender="user")
        self.input_box.delete(0, tk.END)
        threading.Thread(target=self.run_flow, args=(user_q,), daemon=True).start()

    def run_flow(self, user_q):
        step_outputs, reply, summary_section = llm_agent.run_agent(
            user_q, session_history=self.session_history, return_summary=True)
        # print("DEBUG-step_outputs:", step_outputs)
        # print("DEBUG-reply:", reply)
        # print("DEBUG-summary:", summary_section)
        for idx, step_output in enumerate(step_outputs):
            self.set_step(idx, step_output)
            self.update_idletasks()
            time.sleep(0.3)
        self.set_step(5)
        self.set_step(5, "LLM回覆完成")
        for idx in range(len(self.step_labels)):
            self.set_step(idx, self.step_outputs[idx] if idx < len(self.step_outputs) else "")
        self.update_summary(summary_section)
        llm_reply_cleaned = clean_llm_reply(reply)
        # ====== 一定要用 after ======
        self.after(0, lambda: self.add_bubble(llm_reply_cleaned, sender="assistant"))

    def _on_mousewheel(self, event):
        # 支援 Windows/macOS/Linux
        if event.num == 4:  # Linux 上滾
            self.chat_canvas.yview_scroll(-1, "units")
        elif event.num == 5:  # Linux 下滾
            self.chat_canvas.yview_scroll(1, "units")
        elif hasattr(event, 'delta'):
            if event.state & 0x1:  # Shift 鍵，橫向捲動
                self.chat_canvas.xview_scroll(int(-1*(event.delta/120)), "units")
            else:
                self.chat_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def clear_history(self):
        # 清空聊天氣泡
        for widget in self.bubble_frame.winfo_children():
            widget.destroy()
        # 步驟燈全部復歸
        for i, lbl in enumerate(self.step_labels):
            lbl.config(text=f"🟢 {self.step_names[i]}", fg="#185abd")
        # 步驟內容與摘要清空
        self.step_outputs = [""] * len(self.step_outputs)
        self.summary_text = ""
        self.session_history = []
        self.summary_records = []
        # 側欄刷新
        if self.step_panel_visible:
            self.update_step_panel()
        # 聊天區補初始提示
        self.add_bubble("請在下方輸入您的查詢需求。", sender="assistant")

def clean_llm_reply(text):
    import re
    # 移除開頭的 #、*、-、多餘分隔線
    text = re.sub(r'^[#\*\- ]+', '', text, flags=re.MULTILINE)
    text = re.sub(r'[\*\-]+', '', text)
    # 合理保留清單符號
    lines = [line.rstrip() for line in text.split('\n')]
    cleaned = []
    for line in lines:
        if re.match(r'^\d+[\.、]', line):  # 數字條列
            cleaned.append(line)
        elif line.strip().startswith('- '):  # - 條列
            cleaned.append(line)
        elif line.strip() == '':
            cleaned.append('')
        else:
            cleaned.append(line)
    # 只用一個空行分段
    return '\n'.join(cleaned)

if __name__ == "__main__":
    MCPChatUI().mainloop()
