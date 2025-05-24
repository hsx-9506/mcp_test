import tkinter as tk
import traceback
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import tkinter.font as tkFont
import cv2
import time
import platform
from tkinter import filedialog
# ======== YOLO 模型套件 =========
from ultralytics import YOLO
from collections import defaultdict
import numpy as np
import math
from concurrent.futures import ThreadPoolExecutor
import json
import subprocess
from openai import OpenAI
import openai
from tkinter import messagebox
from datetime import datetime
import sys
import os
import locale
import io
import threading
from collections import deque
import glob
import logging
from ultralytics.utils import LOGGER

# ========== (A) 卡爾曼濾波 + 離群值檢測 ==========
class KalmanFilter2D:
    """
    用於平滑 2D 座標 (x, y)，狀態包含 [x, y, vx, vy]
    """
    def __init__(self, dt=1.0, process_noise=1.0, measurement_noise=1.0):
        self.state = np.zeros((4, 1), dtype=float)
        self.F = np.array([
            [1, 0, dt, 0],
            [0, 1, 0, dt],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ], dtype=float)
        self.P = np.eye(4, dtype=float) * 500.0
        self.Q = np.eye(4, dtype=float) * process_noise
        self.H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0]
        ], dtype=float)
        self.R = np.eye(2, dtype=float) * measurement_noise

    def predict(self):
        self.state = self.F @ self.state
        self.P = self.F @ self.P @ self.F.T + self.Q

    def update(self, z):
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        y = z - (self.H @ self.state)  # 殘差
        self.state = self.state + K @ y
        I = np.eye(4)
        self.P = (I - K @ self.H) @ self.P

    def get_state(self):
        return self.state.ravel()

    def set_state(self, x, y, vx=0.0, vy=0.0):
        self.state = np.array([[x], [y], [vx], [vy]], dtype=float)

def outlier_rejection(measurement, prev_filtered, threshold=80.0):
    x_m, y_m = measurement
    x_f, y_f = prev_filtered
    dist = math.hypot(x_m - x_f, y_m - y_f)
    if dist > threshold:
        return "reinit", (x_m, y_m)
    else:
        return "use", (x_m, y_m)

class TestSystemUI:
    def __init__(self, root):
        sys.stdout.reconfigure(encoding='utf-8')
        self.root = root
        self.root.title("測試系統 UI - 卡爾曼濾波 + 離群值過濾 (精簡版)")
        self.root.geometry("1300x690")
        self.root.option_add("*Font", ("Microsoft JhengHei", 14))
        # 設定全域預設背景與文字色彩
        self.root.option_add("*Background", "#2B2B2B")
        self.root.option_add("*Foreground", "white")
        #self.root.configure(bg="#2B2B2B")
        self.confidence_threshold = tk.DoubleVar(value=0.5)
        self.frame_counter = 0
        # 設定 ttk 風格 (使用 clam 主題較易客製化)
        style = ttk.Style()
        style.theme_use("clam")
        LOGGER.setLevel(logging.WARNING)
        #notebook
        self.root.after(5000, self.save_current_status)  # 🟢 5 秒更新快取
        self.root.after(600000, self.save_historical_status)  # 🟡 10 分鐘存中繼歷史
        self.frame_buffer = []  # 每幀記錄的暫存清單
        self.root.after(10000, self.save_frame_buffer)  # 每10秒儲存一次
        self.recent_5min_records = deque(maxlen=300)
        self.root.after(1800000, self.periodic_half_hour_save)  # 每 30 分鐘


        #======LLM======
        openai.api_key ="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"

        self.assistant_id = "asst_plfutQSysIvgOAiiFGPU0aHI"

        self.client = OpenAI(api_key=openai.api_key)
        self.chat_messages = [
            {"role": "system", "content": "你是「精實製造顧問 & 生成式 AI 協作導師」，擅長快速整合視覺巡檢、ERP與產線數據進行精準回應與決策輔助。"
                                            "你會依據使用者問題的性質自動調整回答長度與深度：對於簡單問題（例如：目前生產數量、設備狀態），僅提供簡短、直接的答案；"
                                            "對於較複雜問題（例如：流程異常、效能瓶頸、優化建議），才進一步提供詳細分析與改善建議。"
                                            "如果發現資料不足且必須取得更多資訊時，請在回覆開頭使用以下旗標："
                                            "'NEED_RECENT_DATA'表示需提供最近5分鐘的JSONL紀錄；"
                                            "'NEED_ERP_DATA'表示需提供ERP相關資料；"
                                            "'NEED_LINE_RT_DATA'表示需提供產線即時感測器資料。"
                                            "可用資料來源（由系統自動注入）：current_status.json、half_hour_*.jsonl、ERP API、產線即時訊號(PLC/IoT)。"
                                            "高優先注意的狀況包括錯誤率明顯升高、流程停滯、ERP呆滯工單、缺料或加班超時。"
                                            "行動項目若需後續追蹤，請使用follow_up_in_days:N註記。"
                                        }
        ]



        # 基本色調設定
        style.configure("TFrame", background="#2B2B2B")
        style.configure("TLabel", background="#2B2B2B", foreground="white")
        style.configure("TButton", background="#2B2B2B", foreground="white")
        style.configure("TNotebook", background="#2B2B2B")
        style.configure("TNotebook.Tab", background="#2B2B2B", foreground="#CCCCCC")
        style.map("Treeview", background=[("selected", "#3A3A3A")])
        style.configure("Treeview", background="#2B2B2B", foreground="white", fieldbackground="#2B2B2B")


        style.configure("Custom.TButton",
                        font=("Microsoft JhengHei", 14, "bold"),
                        padding=(10, 8),
                        foreground="#000000",  # 黑色字體
                        background="#FFFFFF",  # 白色背景
                        borderwidth=2,
                        relief="raised")  # 有凸起效果，讓按鈕更立體

        style.map("TNotebook.Tab",
                  foreground=[("selected", "black")],
                  background=[("selected", "#E0E0E0")])  # 選中時使用稍微深一點的背景
        # --------------------------
        # (1) 組裝零件清單（初始為空）
        # --------------------------
        self.available_parts = []
        self.video_path = ""  # 儲存本地影片路徑

        # --------------------------
        # (2) 初始化 YOLO 模型
        # --------------------------
        self.OBJECT_MODEL_PATH = r"C:\Users\s9917\PycharmProjects\Production_report\model\best0428實驗室內量測v1.pt"
        self.POSE_MODEL_PATH = r'C:\Users\s9917\PycharmProjects\Production_report\model\yolo11n-pose.pt'
        self.object_model = YOLO(self.OBJECT_MODEL_PATH)
        self.pose_model = YOLO(self.POSE_MODEL_PATH)
        self.object_model.conf = 0.3
        self.pose_model.conf = 0.3
        self.pose_box_width = 150  # 預設寬度
        self.pose_box_height = 150  # 預設高度
        self.show_pose_zone = True  # 是否顯示 Pose 區域
        # 匯入 YOLO 標籤 (object_model)
        yolo_labels = list(self.object_model.names.values())
        for lb in yolo_labels:
            if lb not in self.available_parts:
                self.available_parts.append(lb)
        # 匯入 YOLO 標籤 (pose_model)
        pose_labels = list(self.pose_model.names.values())
        for plb in pose_labels:
            if plb not in self.available_parts:
                self.available_parts.append(plb)

        # 其他初始變數
        self.all_emp_records = []
        self.emp_photos = {}
        self.dragging_item = None
        self.ghost = None
        self.monitor_paused = False  # ⏸ 是否暫停辨識
        self.error_id_counter = 0
        self.total_completed = 0
        self.total_errors = 0
        self.total_time = 0.0
        self.debug_logs = []
        self.current_box = None
        self.box_in_B = None
        self.last_picked_label = None
        self.current_state = "A"
        self.hand_enter_count = 0
        self.hand_out_count = 0
        self.current_box_left = None
        self.current_box_right = None
        self.line_preview_canvas = None
        self.line_preview_mode = "Y"  # 可未來支援 "X"
        self.line_preview_image = None  # 存放 PhotoImage
        self.pose_y_threshold = 300  # 可以讓使用者在設定頁面調整
        self.y_threshold_var = tk.IntVar(value=300)
        self.x_threshold_var = tk.IntVar(value=200)  # 加這個

        self.monitor_running = False
        self.paused = False
        self.last_status_message = "等待偵測..."
        # 狀態機
        self.current_state = 'A'
        self.hand_enter_count = 0
        self.hand_enter_threshold = 2
        self.action_start_time = 0
        self.action_end_time = 0
        self.action_duration = 0
        self.box_in_B = None

        self.assembly_steps = []
        self.current_step_index = 0
        self.last_picked_label = None
        self.relevant_parts = set()

        # 多幀穩定化 for 盒子
        self.box_stability_counters = defaultdict(int)
        self.box_stability_threshold = 6

        # 建立左右手腕的卡爾曼濾波器
        self.left_wrist_kf = KalmanFilter2D(dt=1.0, process_noise=5.0, measurement_noise=5.0)
        self.right_wrist_kf = KalmanFilter2D(dt=1.0, process_noise=5.0, measurement_noise=5.0)
        self.left_kf_inited = False
        self.right_kf_inited = False

        self.left_wrist_history = []
        self.right_wrist_history = []
        self.hand_out_count = 0
        self.min_out_frames = 2

        # 建立非同步執行緒池與共用變數，用於背景 YOLO 辨識
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.latest_detection = None

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True)

        # (A) 組裝順序設定
        self.tab_assembly = tk.Frame(self.notebook, bg="#2B2B2B")
        self.notebook.add(self.tab_assembly, text="組裝順序設定")
        self.create_assembly_tab(self.tab_assembly)

        # (B) 監控
        self.tab_monitor = tk.Frame(self.notebook, bg="#2B2B2B")
        self.notebook.add(self.tab_monitor, text="監控")
        self.create_monitor_tab(self.tab_monitor)

        # (C) 員工登記
        self.tab_employee = tk.Frame(self.notebook, bg="#2B2B2B")
        self.notebook.add(self.tab_employee, text="員工登記")
        self.create_employee_tab(self.tab_employee)
        # (D) debug
        self.tab_debug = tk.Frame(self.notebook, bg="#2B2B2B")
        self.notebook.add(self.tab_debug, text="變數狀態")
        self.create_debug_tab(self.tab_debug)


        # 每3秒自動呼叫一次 (可自行使用)
        self.root.after(3000, self.reset_detected_parts)

        self.frame_rate = 30
        self.invincible_time_general = int(3 * self.frame_rate)
        # (E) 設定
        self.tab_settings = tk.Frame(self.notebook, bg="#2B2B2B")
        self.notebook.add(self.tab_settings, text="設定")
        self.create_settings_tab(self.tab_settings)

        self.box_lock_enabled = False
        self.locked_boxes = {}
        self.root.after(500, self.auto_update_line_preview)
        self.tab_errorlist = tk.Frame(self.notebook, bg="#2B2B2B")
        self.notebook.add(self.tab_errorlist, text="錯誤列表")
        self.create_error_list_tab(self.tab_errorlist)
    def auto_update_line_preview(self):
        self.update_line_preview()
        self.root.after(500, self.auto_update_line_preview)

    def reset_detected_parts(self):
        # 這裡暫時沒做任何事
        self.root.after(3000, self.reset_detected_parts)

    def log_debug_message(self, level, message):
        timestamp = time.strftime("%H:%M:%S")
        full_msg = f"[{timestamp}] [{level}] {message}"
        if not hasattr(self, 'debug_logs'):
            self.debug_logs = []  # 避免未初始化
        self.debug_logs.append((timestamp, level, full_msg))
        self.filter_debug_log()

    def update_kalman_for_wrist(self, kf_obj, x_m, y_m, inited_attr, threshold=80.0):
        if not getattr(self, inited_attr):
            kf_obj.set_state(x_m, y_m, 0, 0)
            setattr(self, inited_attr, True)
            return x_m, y_m

        kf_obj.predict()
        x_f_prev, y_f_prev, vx_f_prev, vy_f_prev = kf_obj.get_state()
        use_m, (xm_clamped, ym_clamped) = outlier_rejection((x_m, y_m), (x_f_prev, y_f_prev), threshold=threshold)
        if use_m == "use":
            z = np.array([[xm_clamped], [ym_c := ym_clamped]], dtype=float)
            kf_obj.update(z)
        elif use_m == "reinit":
            kf_obj.set_state(xm_clamped, ym_clamped, 0, 0)
        x_f, y_f, vx_f, vy_f = kf_obj.get_state()
        return x_f, y_f

    # ------------------------------
    # 非同步 YOLO 辨識相關函式
    # ------------------------------
    def run_yolo_detection(self, frame):
        try:
            object_results = self.object_model(frame, imgsz=960)[0]
            pose_results = self.pose_model(frame, imgsz=960)[0]
            return {'object_results': object_results, 'pose_results': pose_results}
        except Exception as e:
            self.log_debug_message("ERROR", f"YOLO 辨識失敗: {e}")
            return None

    def _update_detection_result(self, result):
        if result is not None:
            self.latest_detection = result
    # ------------------------------------------------
    # (1) 組裝順序設定
    # ------------------------------------------------
    def create_assembly_tab(self, parent):
        assembly_frame = tk.Frame(parent, bg="#2B2B2B")
        assembly_frame.pack(padx=10, pady=10, fill="both", expand=True)
        main_container = tk.Frame(assembly_frame, bg="#2B2B2B")
        main_container.pack(fill="both", expand=True)

        tree_frame = tk.Frame(main_container, bd=2, relief="groove", bg="#2B2B2B")
        tree_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=5)
        main_container.grid_rowconfigure(0, weight=1)
        main_container.grid_columnconfigure(0, weight=3)

        style = ttk.Style()
        style.configure("Treeview.Heading", font=("Microsoft JhengHei", 16, "bold"))
        style.configure("Treeview", font=("Microsoft JhengHei", 13))

        self.assembly_tree = ttk.Treeview(
            tree_frame, columns=("序號", "零件", "數量"), show="headings", height=15
        )
        self.assembly_tree.heading("序號", text="序號")
        self.assembly_tree.column("序號", width=50, anchor="center")
        self.assembly_tree.heading("零件", text="零件")
        self.assembly_tree.column("零件", width=150, anchor="center")
        self.assembly_tree.heading("數量", text="數量")
        self.assembly_tree.column("數量", width=80, anchor="center")
        self.assembly_tree.pack(fill="both", expand=True)

        tree_scrollbar = tk.Scrollbar(tree_frame, orient="vertical",
                                      command=self.assembly_tree.yview, bg="#2B2B2B")
        tree_scrollbar.pack(side="right", fill="y")
        self.assembly_tree.config(yscrollcommand=tree_scrollbar.set)

        self.assembly_tree.tag_configure("evenrow", background="#333333")
        self.assembly_tree.tag_configure("oddrow", background="#2B2B2B")

        self.update_assembly_numbers()
        self.apply_row_striping()

        # 綁定拖曳事件（上下拖曳）
        self.assembly_tree.bind("<ButtonPress-1>", self.on_treeview_button_press)
        self.assembly_tree.bind("<B1-Motion>", self.on_treeview_b1_motion)
        self.assembly_tree.bind("<ButtonRelease-1>", self.on_treeview_button_release)

        right_container = tk.Frame(main_container, bd=2, relief="groove", bg="#2B2B2B")
        right_container.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=5)
        main_container.grid_columnconfigure(1, weight=1)

        new_container = tk.Frame(right_container, bg="#2B2B2B")
        new_container.pack(fill="x", pady=5, padx=5, anchor="e")

        # 新增/刪除零件
        new_part_frame = tk.LabelFrame(new_container, text="新增/刪除零件",
                                       font=("Microsoft JhengHei", 14, "bold"),
                                       bg="#2B2B2B", fg="white")
        new_part_frame.pack(fill="x", pady=2, anchor="e")

        tk.Label(new_part_frame, text="零件名稱:", font=("Microsoft JhengHei", 15, "bold"),
                 bg="#2B2B2B", fg="white").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.new_part_entry = tk.Entry(new_part_frame, font=("Microsoft JhengHei", 15), bg="#2B2B2B", fg="white")
        self.new_part_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        new_part_btn = ttk.Button(new_part_frame, text="加入零件", style="Custom.TButton",

                                  command=self.add_new_part)
        new_part_btn.grid(row=0, column=2, padx=5, pady=5)

        delete_part_btn = ttk.Button(new_part_frame, text="刪除零件", style="Custom.TButton",

                                     command=self.delete_new_part)
        delete_part_btn.grid(row=0, column=3, padx=5, pady=5)

        # 新增組裝項目
        new_item_frame = tk.LabelFrame(new_container, text="新增組裝項目",
                                       font=("Microsoft JhengHei", 14, "bold"),
                                       bg="#2B2B2B", fg="white")
        new_item_frame.pack(fill="x", pady=2, anchor="e")

        tk.Label(new_item_frame, text="零件:", font=("Microsoft JhengHei", 15, "bold"),
                 bg="#2B2B2B", fg="white").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.part_combobox = ttk.Combobox(
            new_item_frame,
            values=self.available_parts,
            state="readonly",
            font=("Microsoft JhengHei", 12)
        )
        self.part_combobox.set("請選擇零件")
        self.part_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        tk.Label(new_item_frame, text="數量:", font=("Microsoft JhengHei", 15, "bold"),
                 bg="#2B2B2B", fg="white").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.qty_var = tk.StringVar(value="1")
        self.qty_spinbox = tk.Spinbox(new_item_frame,
                                      from_=1, to=100, width=5,
                                      font=("Microsoft JhengHei", 15),
                                      textvariable=self.qty_var, bg="#2B2B2B", fg="white")
        self.qty_spinbox.grid(row=0, column=3, padx=5, pady=5, sticky="w")

        add_btn = ttk.Button(new_item_frame, text="新增", style="Custom.TButton",

                             command=self.add_assembly_item)
        add_btn.grid(row=0, column=4, padx=5, pady=5)

        # 最終完成品
        final_product_frame = tk.LabelFrame(right_container, text="最終完成品",
                                            font=("Microsoft JhengHei", 14, "bold"),
                                            bg="#2B2B2B", fg="white")
        final_product_frame.pack(fill="x", pady=5, padx=5)

        tk.Label(final_product_frame, text="最終完成品: ",
                 font=("Microsoft JhengHei", 15, "bold"),
                 bg="#2B2B2B", fg="white").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.final_product_combobox = ttk.Combobox(
            final_product_frame,
            values=self.available_parts,
            state="readonly",
            font=("Microsoft JhengHei", 12)
        )
        self.final_product_combobox.set("請選擇最終完成品")
        self.final_product_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # 操作按鈕
        op_frame = tk.LabelFrame(right_container, text="操作按鈕",
                                 font=("Microsoft JhengHei", 14, "bold"),
                                 bg="#2B2B2B", fg="white")
        op_frame.pack(fill="x", pady=5, padx=5)

        up_btn = ttk.Button(op_frame, text="上移", style="Custom.TButton", command=self.move_assembly_up, width=6)
        up_btn.pack(side="left", padx=2, pady=2)

        down_btn = ttk.Button(op_frame, text="下移", style="Custom.TButton", command=self.move_assembly_down, width=6)
        down_btn.pack(side="left", padx=2, pady=2)

        delete_btn = ttk.Button(op_frame, text="刪除", style="Custom.TButton", command=self.delete_assembly_item,
                                width=6)
        delete_btn.pack(side="left", padx=2, pady=2)

        confirm_btn = ttk.Button(op_frame, text="確定", style="Custom.TButton", command=self.confirm_assembly,
                                 width=6)
        confirm_btn.pack(side="left", padx=2, pady=2)

        reset_btn = ttk.Button(op_frame, text="重置", style="Custom.TButton", command=self.reset_assembly, width=6)
        reset_btn.pack(side="left", padx=2, pady=2)

    def add_new_part(self):
        new_part = self.new_part_entry.get().strip()
        if new_part:
            if new_part not in self.available_parts:
                self.available_parts.append(new_part)
                self.part_combobox['values'] = self.available_parts
                self.final_product_combobox['values'] = self.available_parts
                messagebox.showinfo("成功", f"已加入新的零件或盒子：{new_part}")
            else:
                messagebox.showwarning("注意", f"{new_part} 已存在！")
            self.new_part_entry.delete(0, tk.END)
        else:
            messagebox.showwarning("警告", "請輸入名稱。")

    def delete_new_part(self):
        part_to_delete = self.new_part_entry.get().strip()
        if part_to_delete:
            if part_to_delete in self.available_parts:
                self.available_parts.remove(part_to_delete)
                self.part_combobox['values'] = self.available_parts
                self.final_product_combobox['values'] = self.available_parts
                messagebox.showinfo("成功", f"已刪除：{part_to_delete}")
            else:
                messagebox.showwarning("注意", f"{part_to_delete} 不存在！")
            self.new_part_entry.delete(0, tk.END)
        else:
            messagebox.showwarning("警告", "請輸入要刪除的名稱。")

    def add_assembly_item(self):
        part = self.part_combobox.get()
        if part == "請選擇零件" or not part:
            messagebox.showwarning("警告", "請先選擇零件或盒子。")
            return
        try:
            quantity = int(self.qty_var.get())
        except ValueError:
            messagebox.showwarning("警告", "請輸入正確的數量。")
            return
        self.assembly_tree.insert('', 'end', values=("", part, quantity))
        self.update_assembly_numbers()
        self.qty_var.set("1")
        self.apply_row_striping()

    def update_assembly_numbers(self):
        for idx, item in enumerate(self.assembly_tree.get_children(), start=1):
            vals = list(self.assembly_tree.item(item, 'values'))
            vals[0] = idx
            self.assembly_tree.item(item, values=vals)

    def apply_row_striping(self):
        for idx, item in enumerate(self.assembly_tree.get_children()):
            if idx % 2 == 0:
                self.assembly_tree.item(item, tags=("evenrow",))
            else:
                self.assembly_tree.item(item, tags=("oddrow",))
        self.assembly_tree.tag_configure("evenrow", background="#333333")
        self.assembly_tree.tag_configure("oddrow", background="#2B2B2B")

    def on_treeview_button_press(self, event):
        self.dragging_item = self.assembly_tree.identify_row(event.y)
        if self.dragging_item:
            vals = self.assembly_tree.item(self.dragging_item, 'values')
            ghost_text = " | ".join(str(v) for v in vals)
            self.ghost = tk.Toplevel(self.root)
            self.ghost.overrideredirect(True)
            self.ghost.wm_attributes("-alpha", 0.7)
            self.ghost.configure(background="#2B2B2B")
            ghost_label = tk.Label(self.ghost, text=ghost_text,
                                   font=("Microsoft JhengHei", 12),
                                   bg="#2B2B2B", fg="white", bd=1, relief="solid")
            ghost_label.pack()
            self.ghost.geometry(f"+{event.x_root + 10}+{event.y_root + 10}")

    def on_treeview_b1_motion(self, event):
        if not self.dragging_item:
            return
        if self.ghost:
            self.ghost.geometry(f"+{event.x_root + 10}+{event.y_root + 10}")
        target_item = self.assembly_tree.identify_row(event.y)
        if target_item and target_item != self.dragging_item:
            target_index = self.assembly_tree.index(target_item)
            self.assembly_tree.move(self.dragging_item, '', target_index)
            self.update_assembly_numbers()
            self.apply_row_striping()

    def on_treeview_button_release(self, event):
        self.dragging_item = None
        if self.ghost:
            self.ghost.destroy()
            self.ghost = None

    def move_assembly_up(self):
        selected = self.assembly_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "請先選擇要上移的項目。")
            return
        for item in selected:
            index = self.assembly_tree.index(item)
            if index > 0:
                self.assembly_tree.move(item, '', index - 1)
        self.update_assembly_numbers()
        self.apply_row_striping()

    def move_assembly_down(self):
        selected = self.assembly_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "請先選擇要下移的項目。")
            return
        items = self.assembly_tree.get_children()
        for item in reversed(selected):
            index = self.assembly_tree.index(item)
            if index < len(items) - 1:
                self.assembly_tree.move(item, '', index + 1)
        self.update_assembly_numbers()
        self.apply_row_striping()

    def delete_assembly_item(self):
        selected = self.assembly_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "請先選擇要刪除的項目。")
            return
        for item in selected:
            self.assembly_tree.delete(item)
        self.update_assembly_numbers()
        self.apply_row_striping()

    def check_assembly_errors(self):
        final_product = self.final_product_combobox.get().strip()
        if not final_product or final_product == "請選擇最終完成品":
            return "尚未選擇最終完成品", "待處理"

        parts_list = []
        for item in self.assembly_tree.get_children():
            seq, part_name, qty = self.assembly_tree.item(item, 'values')
            parts_list.append(part_name)

        if final_product not in parts_list:
            return f"缺少最終完成品：{final_product}", "待處理"
        else:
            return "無錯誤", "已處理"

    def confirm_assembly(self):
        items = self.assembly_tree.get_children()

        if not items:
            messagebox.showwarning("警告", "目前沒有設定任何組裝順序。")
            return

        error_message, status = self.check_assembly_errors()
        if status == "待處理":
            messagebox.showwarning("警告", f"{error_message}，請確認後再組裝。")
            return

        self.assembly_steps = []


        for item in items:
            seq, part, quantity = self.assembly_tree.item(item, 'values')
            quantity = int(quantity)
            step_info = {"part": part, "qty": quantity}
            self.assembly_steps.append(step_info)
            self.relevant_parts.add(part)
            final_product = self.final_product_combobox.get().strip()
            if final_product and final_product != "請選擇最終完成品":
                self.relevant_parts.add(final_product)  # ✅ 把 fin_box 也納入

        self.current_step_index = 0
        order_str = " → ".join([f"{d['part']} x{d['qty']}" for d in self.assembly_steps])
        messagebox.showinfo("設定確認", f"組裝順序已確認。\n{order_str}")

    def reset_assembly(self):
        for item in self.assembly_tree.get_children():
            self.assembly_tree.delete(item)
        self.part_combobox.set("請選擇零件")
        self.qty_var.set("1")
        self.final_product_combobox.set("請選擇最終完成品")
        self.assembly_steps = []
        self.current_step_index = 0
        self.relevant_parts = set()
        messagebox.showinfo("重置", "組裝順序已重置。")

    # ------------------------------------------------
    # (2) 監控分頁
    # ------------------------------------------------
    def create_monitor_tab(self, parent):
        monitor_grid = tk.Frame(parent, bg="#2B2B2B")
        monitor_grid.pack(fill="both", expand=True)

        monitor_grid.columnconfigure(0, weight=1, uniform="col")
        monitor_grid.columnconfigure(1, weight=1, uniform="col")
        monitor_grid.rowconfigure(0, weight=1, uniform="row")
        monitor_grid.rowconfigure(1, weight=1, uniform="row")

        self.left_top_frame = tk.LabelFrame(monitor_grid, text="即時影像辨識區",
                                            font=("Microsoft JhengHei", 14, "bold"),
                                            bg="#2B2B2B", fg="white")
        self.left_top_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.rt_image_label = tk.Label(self.left_top_frame, bg="#2B2B2B")
        self.rt_image_label.pack(fill="both", expand=True, padx=5, pady=5)

        self.cap = None
        self.camera_url = "rtsp://ncutimact@gmail.com:Abc557786@192.168.50.193:554/stream2"

        self.right_top_frame = tk.LabelFrame(monitor_grid, text="即時狀態",
                                             font=("Microsoft JhengHei", 14, "bold"),
                                             bg="#2B2B2B", fg="white")
        self.right_top_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.status_label = tk.Label(self.right_top_frame, text="等待偵測...",
                                     font=("Microsoft JhengHei", 25, "bold"),
                                     fg="white", bg="#2B2B2B", wraplength=480,
                                     justify="center", anchor="center")
        self.status_label.pack(fill="both", expand=True, padx=5, pady=5)
        self.debug_label = tk.Label(self.right_top_frame, text="",
                                    font=("Microsoft JhengHei", 12, "bold"),
                                    fg="white", bg="#2B2B2B",
                                    justify="center", anchor="center")
        self.debug_label.pack(fill="both", expand=True, padx=5, pady=5)

        start_button = ttk.Button(self.right_top_frame,style="Custom.TButton", text="開始偵測",
                                  command=self.start_monitoring)
        start_button.pack(pady=5)
        pause_button = ttk.Button(self.right_top_frame,style="Custom.TButton", text="⏸ 暫停",
                                  command=self.toggle_pause)
        pause_button.pack(pady=5)
        self.pause_button = pause_button
        # 以下是接續原始專案的補充程式碼，插入在 TestSystemUI 中
        # =============================================
        # 1. 在 create_monitor_tab 中新增按鈕
        # =============================================
        open_debug_btn = ttk.Button(
            self.right_top_frame,
            text="開啟錯誤分析視窗",style="Custom.TButton",
            command=self.create_error_analysis_window
        )
        open_debug_btn.pack(pady=5)
        self.left_bottom_frame = tk.LabelFrame(monitor_grid, text="數據分析",
                                               font=("Microsoft JhengHei", 14, "bold"),
                                               bg="#2B2B2B", fg="white")
        self.left_bottom_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.create_analysis_tab(self.left_bottom_frame)  # ✅ 新增這行

        self.right_bottom_frame = tk.LabelFrame(monitor_grid, text="統計資訊",
                                                font=("Microsoft JhengHei", 14, "bold"),
                                                bg="#2B2B2B", fg="white")
        self.right_bottom_frame.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)

        self.total_time_label = tk.Label(
            self.right_bottom_frame, text="Total Time: 0.0 s",
            font=("Microsoft JhengHei", 16, "bold"), fg="white", bg="#2B2B2B"
        )
        self.total_time_label.pack(pady=10, anchor="w")

        self.completion_label = tk.Label(
            self.right_bottom_frame, text="完成件數: 0",
            font=("Microsoft JhengHei", 16, "bold"), fg="white", bg="#2B2B2B"
        )
        self.completion_label.pack(pady=10, anchor="w")

        self.error_count_label = tk.Label(
            self.right_bottom_frame, text="錯誤件數: 0",
            font=("Microsoft JhengHei", 16, "bold"), fg="white", bg="#2B2B2B"
        )
        self.error_count_label.pack(pady=10, anchor="w")
        # 定義信心值變數
        self.confidence_threshold = tk.DoubleVar(value=0.5)
        # 建立 slider（使用 ttk.Scale）
        confidence_scale = ttk.Scale(
            self.right_bottom_frame, from_=0.1, to=1.0, orient="horizontal",
            variable=self.confidence_threshold
        )
        confidence_scale.pack(pady=10)
        # 建立 slider 說明標籤
        confidence_label = tk.Label(self.right_bottom_frame, text="信心值閥值調整", bg="#2B2B2B", fg="white")
        confidence_label.pack()
        self.status_label.config(text="請選擇影片來源並點選『開始偵測』", fg="gray")

    def toggle_pause(self):
        if self.monitor_running:
            self.monitor_paused = not self.monitor_paused
            if self.monitor_paused:
                self.pause_button.config(text="▶️ 繼續")
                self.status_label.config(text="已暫停", fg="yellow")
            else:
                self.pause_button.config(text="⏸ 暫停")
                self.status_label.config(text="偵測中...", fg="white")
        # =============================================
        # 2. 錯誤分析視窗
        # =============================================


    def create_error_analysis_window(self):

        self.error_window = tk.Toplevel(self.root)
        self.error_window.title("錯誤分析視窗")
        self.error_window.geometry("700x400")
        self.error_window.configure(bg="#1E1E1E")
        self.error_window.protocol("WM_DELETE_WINDOW", self.on_close_debug_window)

        filter_frame = tk.Frame(self.error_window, bg="#1E1E1E")
        filter_frame.pack(fill="x", pady=5)

        tk.Label(filter_frame, text="顯示等級：", bg="#1E1E1E", fg="white").pack(side="left", padx=(10, 5))
        self.level_var = tk.StringVar(value="ALL")
        level_options = ttk.Combobox(filter_frame, textvariable=self.level_var,
                                     values=["ALL", "INFO", "WARNING", "ERROR","filter","偵測結果"], width=10, state="readonly")
        level_options.pack(side="left")
        level_options.bind("<<ComboboxSelected>>", lambda e: self.filter_debug_log())

        self.debug_text = tk.Text(self.error_window, bg="#1E1E1E", fg="white",
                                  font=("Consolas", 11), wrap="none")
        self.debug_text.pack(fill="both", expand=True)

        self.debug_scroll = tk.Scrollbar(self.error_window, command=self.debug_text.yview)
        self.debug_text.config(yscrollcommand=self.debug_scroll.set)
        self.debug_scroll.pack(side="right", fill="y")

        self.debug_logs = []  # [(timestamp, level, message)]
        self.log_visible = False

        # 翻牌按鈕
        self.toggle_log_btn = ttk.Button(
            self.error_window,
            text="展開錯誤日誌",style="Custom.TButton",
            command=self.toggle_debug_log_display
        )
        self.toggle_log_btn.pack(pady=5)

        # 篩選區域（固定）
        filter_frame = tk.Frame(self.error_window, bg="#1E1E1E")
        filter_frame.pack(fill="x", pady=(0, 5))

        tk.Label(filter_frame, text="顯示等級：", bg="#1E1E1E", fg="white").pack(side="left", padx=(10, 5))
        self.level_var = tk.StringVar(value="ALL")
        level_options = ttk.Combobox(filter_frame, textvariable=self.level_var,
                                     values=["ALL", "INFO", "WARNING", "ERROR","filtered","偵測結果"],
                                     width=10, state="readonly")
        level_options.pack(side="left")
        level_options.bind("<<ComboboxSelected>>", lambda e: self.filter_debug_log())

        # Log 區域（固定但預設隱藏）
        self.debug_frame_container = tk.Frame(self.error_window, bg="#1E1E1E")
        self.debug_text = tk.Text(self.debug_frame_container, bg="#1E1E1E", fg="white",
                                  font=("Consolas", 11), wrap="none")
        self.debug_scroll = tk.Scrollbar(self.debug_frame_container, command=self.debug_text.yview)
        self.debug_text.config(yscrollcommand=self.debug_scroll.set)

        # 預設先不 pack（會在按鈕按下才顯示）
        self.debug_frame_container.pack(fill="both", expand=True)

    def on_close_debug_window(self):
        self.debug_text = None
        self.debug_scroll = None
        self.error_window.destroy()
    # =============================================
    # 3. 新增錯誤記錄函式（等級分類）
    # =============================================
    def log_debug_message(self, level, message):
        timestamp = time.strftime("%H:%M:%S")
        full_msg = f"[{timestamp}] [{level}] {message}"
        self.debug_logs.append((timestamp, level, full_msg))
        self.filter_debug_log()  # 即時更新
        if hasattr(self, 'debug_text') and self.debug_text.winfo_exists():
            self.filter_debug_log()

    # =============================================
    # 4. 等級過濾更新函式
    # =============================================
    def filter_debug_log(self):
        if not hasattr(self, 'debug_text'):
            return
        if not self.debug_text.winfo_exists():  # ✅ 檢查元件是否還活著
            return

        level_filter = self.level_var.get() if hasattr(self, 'level_var') else "ALL"
        self.debug_text.config(state="normal")
        self.debug_text.delete("1.0", tk.END)
        for t, lvl, msg in self.debug_logs:
            if level_filter == "ALL" or lvl == level_filter:
                self.debug_text.insert(tk.END, msg + "\n")
        self.debug_text.see(tk.END)
        self.debug_text.config(state="disabled")

    def toggle_debug_log_display(self):
        if self.log_visible:
            self.debug_text.pack_forget()
            self.debug_scroll.pack_forget()
            self.toggle_log_btn.config(text="展開錯誤日誌")
        else:
            self.debug_text.pack(side="left", fill="both", expand=True)
            self.debug_scroll.pack(side="right", fill="y")
            self.toggle_log_btn.config(text="收起錯誤日誌")
        self.log_visible = not self.log_visible

    def start_monitoring(self):
        if not self.monitor_running:
            source = self.video_source_var.get()
            if source == "local":
                if not self.video_path:
                    messagebox.showwarning("警告", "請先選擇本地影片檔案")
                    return
                self.cap = cv2.VideoCapture(self.video_path)

            elif source == "stream":
                self.camera_url = self.rtsp_url_var.get()
                self.cap = cv2.VideoCapture(self.camera_url)

            elif source == "usb":
                self.cap = cv2.VideoCapture(0)  # 攝影機編號 0（可視情況換成1,2...）

            if not self.cap.isOpened():
                messagebox.showerror("錯誤", "無法讀取影片來源")
                return

            self.video_fps = self.cap.get(cv2.CAP_PROP_FPS)
            if self.video_fps <= 0:
                self.video_fps = 30

            self.monitor_running = True
            self.status_label.config(text="偵測中...", fg="white")
            self.update_video()
            self.update_cumulative_info()

    def resume_monitoring(self):
        self.paused = False
        self.last_status_message = "等待偵測..."
        self.pause_button = None
        self.status_label.config(text=self.last_status_message, fg="white")
        self.update_video()
        self.update_cumulative_info()
    def update_debug_vars(self):
        for var_name in self.debug_vars:
            try:
                val = eval(f"self.{var_name}")
            except Exception as e:
                val = f"⚠ 無法讀取 ({e})"
            self.debug_labels[var_name].config(text=f"{var_name}: {val}")

    def run_yolo_detection(self, frame):
        try:
            object_results = self.object_model(frame, imgsz=960)[0]
            pose_results = self.pose_model(frame, imgsz=960)[0]
            return {'object_results': object_results, 'pose_results': pose_results}
        except Exception as e:
            self.log_debug_message("ERROR", f"YOLO 推論爆錯啦！ {e}")
            return None
    def update_video(self):
        self.frame_counter += 1
        ret, frame = self.cap.read()

        if not self.monitor_running or self.paused:
            return
        if self.monitor_paused:
            delay = int(1000 / self.video_fps)
            self.rt_image_label.after(delay, self.update_video)
            return

        if self.video_source_var.get() == "stream":
            for _ in range(3):
                self.cap.grab()

        ret, frame = self.cap.read()
        if not ret:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self.rt_image_label.after(int(1000 / self.video_fps), self.update_video)
            return
        if self.frame_counter % 3 == 0:
            # 每 5 幀做一次 YOLO 推論（避免每幀都做）
            self.executor.submit(self.run_yolo_detection, frame.copy()).add_done_callback(
                lambda f: self._update_detection_result(f.result())
            )

        # ============ YOLO & Pose 同步辨識 ============
        detection = self.latest_detection or self.run_yolo_detection(frame.copy())
        self.latest_detection = detection
        object_results = detection["object_results"]
        pose_results = detection["pose_results"]

        # ============ 處理多幀穩定化框框 ============
        current_frame_detected = {}
        for b in object_results.boxes:
            cid = int(b.cls[0])
            label_name = self.object_model.names[cid]
            x1, y1, x2, y2 = b.xyxy[0].cpu().numpy()
            confidence = float(b.conf[0].cpu().numpy())
            if label_name in self.relevant_parts and confidence >= self.confidence_threshold.get():
                if label_name not in current_frame_detected or confidence > current_frame_detected[label_name][4]:
                    current_frame_detected[label_name] = (x1, y1, x2, y2, confidence)

        for label in self.relevant_parts:
            if label in current_frame_detected:
                self.box_stability_counters[label] = min(self.box_stability_counters[label] + 1, 9999)
            else:
                self.box_stability_counters[label] = max(self.box_stability_counters[label] - 1, 0)

        used_boxes = {}
        for label in self.relevant_parts:
            if self.box_stability_counters[label] >= self.box_stability_threshold:
                if label in current_frame_detected:
                    x1, y1, x2, y2, conf = current_frame_detected[label]
                    used_boxes[label] = (x1, y1, x2, y2)
                    cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                    cv2.putText(frame, f"{label} {conf:.2f}", (int(x1), int(y1) - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # ============ Pose 辨識 + Kalman + 濾波 ============
        # 預設 None，避免後面炸掉
        keypoints = None
        left_hand = right_hand = None

        if pose_results and hasattr(pose_results, "keypoints") and pose_results.keypoints is not None:
            try:
                keypoints = pose_results.keypoints.xy.cpu().numpy()
                self.log_debug_message("偵測結果", f"Pose keypoints shape = {keypoints.shape}")
                if keypoints.shape[0] > 0:
                    # 中心選最近那個人
                    center_x = frame.shape[1] / 2
                    center_y = frame.shape[0] / 2
                    min_dist = float('inf')
                    best_person = None
                    for person in keypoints:
                        for x, y in person:
                            cv2.circle(frame, (int(x), int(y)), 3, (0, 255, 0), -1)

                    for i, person_keypoints in enumerate(keypoints):
                        x_mean = np.mean(person_keypoints[:, 0])
                        y_mean = np.mean(person_keypoints[:, 1])
                        dist = np.hypot(x_mean - center_x, y_mean - center_y)
                        if dist < min_dist:
                            min_dist = dist
                            best_person = person_keypoints

                    if best_person is not None and best_person.shape[0] > 10:
                        lw = best_person[9]
                        rw = best_person[10]
                        x_lf, y_lf = self.update_kalman_for_wrist(self.left_wrist_kf, lw[0], lw[1], 'left_kf_inited')
                        x_rf, y_rf = self.update_kalman_for_wrist(self.right_wrist_kf, rw[0], rw[1], 'right_kf_inited')
                        left_hand = (x_lf, y_lf)
                        right_hand = (x_rf, y_rf)
                        cv2.circle(frame, (int(x_lf), int(y_lf)), 6, (255, 0, 0), -1)
                        cv2.circle(frame, (int(x_rf), int(y_rf)), 6, (0, 0, 255), -1)
            except Exception as e:
                self.log_debug_message("ERROR", f"Pose keypoints 解析錯誤: {e}")

        # ✅ 只有 keypoints 有成功才畫出原始點位（防炸）
        if keypoints is not None and keypoints.shape[0] > 0:
            for x, y in keypoints[0]:
                cv2.circle(frame, (int(x), int(y)), 3, (0, 255, 0), -1)

        # ============ 偵測進入區域就鎖定 ============
        y_thres = self.y_threshold_var.get()
        x_thres = self.x_threshold_var.get()
        mode = self.line_preview_mode_var.get()

        def is_hand_in_area(hand):
            if hand is None:
                return False
            x, y = hand
            w = self.pose_area_w_var.get()
            h = self.pose_area_h_var.get()
            cx, cy = x, y
            x1 = cx - w // 2
            x2 = cx + w // 2
            y1 = cy - h // 2
            y2 = cy + h // 2
            return (y2 >= y_thres if mode == "Y" else x2 >= x_thres)

        if is_hand_in_area(left_hand) or is_hand_in_area(right_hand):
            if not self.box_lock_enabled:
                self.locked_boxes = used_boxes.copy()
                self.box_lock_enabled = True
        else:
            if self.box_lock_enabled:
                self.box_lock_enabled = False

        # ============ 框框判斷與狀態機 ============
        current_box_left = current_box_right = None
        for hand, name, color in [(left_hand, "Left", (255, 0, 0)), (right_hand, "Right", (0, 0, 255))]:
            if hand:
                x, y = int(hand[0]), int(hand[1])
                w = self.pose_area_w_var.get()
                h = self.pose_area_h_var.get()
                cv2.rectangle(frame, (x - w // 2, y - h // 2), (x + w // 2, y + h // 2), (255, 255, 0), 2)
                for lbl, (bx1, by1, bx2, by2) in used_boxes.items():
                    # 手部偵測區（以手中心為中心）
                    x1_hand = x - w // 2
                    y1_hand = y - h // 2
                    x2_hand = x + w // 2
                    y2_hand = y + h // 2

                    # 判斷手部框與 box 是否有交集
                    intersect = not (x2_hand < bx1 or x1_hand > bx2 or y2_hand < by1 or y1_hand > by2)
                    if intersect:
                        if name == "Left":
                            current_box_left = lbl
                        else:
                            current_box_right = lbl
                        cv2.putText(frame, f"{name} Hand: {lbl}", (20, 30 if name == "Left" else 60),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                        break

        if right_hand:
            self.do_state_machine(right_hand[0], right_hand[1], current_box_right)
        elif left_hand:
            self.do_state_machine(left_hand[0], left_hand[1], current_box_left)

        # ============ 畫出偵測線 ============
        if mode == "Y":
            cv2.line(frame, (0, y_thres), (frame.shape[1], y_thres), (0, 255, 255), 2)
            cv2.arrowedLine(frame, (frame.shape[1] - 20, y_thres - 20), (frame.shape[1] - 20, y_thres + 10),
                            (0, 255, 255), 2)
            cv2.putText(frame, f"Y={y_thres}", (10, y_thres - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        else:
            cv2.line(frame, (x_thres, 0), (x_thres, frame.shape[0]), (0, 255, 255), 2)
            cv2.arrowedLine(frame, (x_thres - 20, 20), (x_thres + 10, 20), (0, 255, 255), 2)
            cv2.putText(frame, f"X={x_thres}", (x_thres + 5, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        # ============ 顯示影像 ============
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_rgb = cv2.resize(frame_rgb, (600, 400))
        img = Image.fromarray(frame_rgb)
        self.rt_image = ImageTk.PhotoImage(img)
        self.rt_image_label.configure(image=self.rt_image)

        self.rt_image_label.after(15, self.update_video)  # 約 60 FPS 更新

    def do_state_machine(self, hand_x, hand_y, current_box):
        self.log_debug_message("STATE", f"[{self.current_state}] current_box = {current_box}, hand_x = {hand_x}, hand_y = {hand_y}")
        self.current_box = current_box
        self.debug_label.config(text=f"State: {self.current_state} | Count: {self.hand_enter_count} | box={current_box}")
        if hand_x is None or hand_y is None:
            self.hand_enter_count = 0
            self.hand_out_count = 0
            return
        if self.current_state == 'A':
            if current_box:
                self.hand_enter_count += 1
                if self.hand_enter_count >= self.hand_enter_threshold:
                    self.current_state = 'B'
                    self.box_in_B = current_box
                    self.hand_enter_count = 0
                    self.hand_out_count = 0
            else:
                self.hand_enter_count = 0
        elif self.current_state == 'B':
            if current_box == self.box_in_B:
                self.hand_out_count = 0
                self.hand_enter_count += 1
                if self.hand_enter_count >= self.hand_enter_threshold:
                    self.current_state = 'C'
                    self.hand_enter_count = 0
                    self.action_start_time = time.time()
                    self.last_picked_label = current_box
            else:
                self.hand_out_count += 1
                if self.hand_out_count >= self.min_out_frames:
                    self.last_picked_label = self.box_in_B
                    self.current_state = 'D'
                    self.hand_out_count = 0
                    self.hand_enter_count = 0
        elif self.current_state == 'C':
            if current_box == self.box_in_B:
                self.hand_out_count = 0
            else:
                self.hand_out_count += 1
                if self.hand_out_count >= self.min_out_frames:
                    self.current_state = 'D'
                    self.action_end_time = time.time()
                    self.action_duration = self.action_end_time - self.action_start_time
                    self.hand_out_count = 0
                    self.hand_enter_count = 0

        elif self.current_state == 'D':
            self.check_and_go_next_step()

            # ✅ 若已完成所有步驟，等手再次伸入第一步驟的盒子時重新開始
            if self.current_step_index >= len(self.assembly_steps):
                first_step = self.assembly_steps[0] if self.assembly_steps else None
                if first_step and current_box == first_step["part"]:
                    # 重置所有步驟的數量（例如全部設為初始數）
                    for item in self.assembly_tree.get_children():
                        seq, part, qty = self.assembly_tree.item(item, 'values')
                        for step in self.assembly_steps:
                            if step["part"] == part:
                                step["qty"] = int(qty)
                    self.current_step_index = 0
                    self.status_label.config(text=f"重新開始！下一步：{first_step['part']}", fg="white")
                    self.last_status_message = f"重新開始！下一步：{first_step['part']}"
            self.current_state = 'A'
            self.box_in_B = None
            self.hand_out_count = 0
            self.hand_enter_count = 0
        self.check_restart_condition(current_box)

    def check_and_go_next_step(self):
        if not self.assembly_steps:
            return
        if self.current_step_index >= len(self.assembly_steps):
            self.status_label.config(text="全部完成！", fg="white")
            self.total_completed += 1
            return
        current_step = self.assembly_steps[self.current_step_index]
        needed_part = current_step["part"]
        if self.last_picked_label == needed_part:
            current_step["qty"] -= 1
            if current_step["qty"] <= 0:

                self.current_step_index += 1
                if self.current_step_index >= len(self.assembly_steps):
                    self.total_completed += 1  # ✅ 每次完整跑完流程就加1
                    self.status_label.config(text="恭喜！全部完成！", fg="white")
                    self.last_status_message = "恭喜！全部完成！"
                else:
                    nxt = self.assembly_steps[self.current_step_index]["part"]
                    self.status_label.config(text=f"完成 {needed_part}，下一步: {nxt}", fg="white")
                    self.last_status_message = f"完成 {needed_part}，下一步: {nxt}"
            else:
                self.status_label.config(text=f"拿到 {needed_part}，尚需 {current_step['qty']} 個", fg="white")
        else:
            if not self.last_picked_label:
                msg = "順序錯誤：好像拿走了未知盒子？"
            else:
                msg = f"錯誤：拿到({self.last_picked_label}) !預期({needed_part})"
            self.status_label.config(text=msg, fg="white")
            self.total_errors += 1
            self.add_error_record(msg)
        self.last_picked_label = None

    def check_restart_condition(self, current_box):
        if not self.assembly_steps:
            return
        if self.current_step_index < len(self.assembly_steps):
            return  # 尚未完成，跳過

        first_step = self.assembly_steps[0]
        if current_box == first_step["part"]:
            # 重新載入 qty
            for item in self.assembly_tree.get_children():
                seq, part, qty = self.assembly_tree.item(item, 'values')
                for step in self.assembly_steps:
                    if step["part"] == part:
                        step["qty"] = int(qty)
            self.current_step_index = 0
            self.status_label.config(text=f"重新開始！下一步：{first_step['part']}", fg="white")
            self.last_status_message = f"重新開始！下一步：{first_step['part']}"
            self.log_debug_message("INFO", "流程重新開始")
    def add_error_record(self, msg):
        self.error_id_counter += 1
        current_time = time.strftime("%H:%M:%S")
        self.error_status_tree.insert("", "end", values=(self.error_id_counter, msg, "待處理", current_time), tags=("待處理",))

    def update_cumulative_info(self):
        if not self.monitor_running:
            return
        self.completion_label.config(text=f"完成件數: {self.total_completed}")

        self.total_time += 1
        self.total_time_label.config(text=f"Total Time: {self.total_time:.1f} s")
        self.error_count_label.config(text=f"錯誤件數: {self.total_errors}")

        self.right_bottom_frame.after(1000, self.update_cumulative_info)

    def complete_selected_error(self, event=None):
        selected = self.error_status_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "請先選擇要完成的錯誤項目。")
            return
        if messagebox.askyesno("確認", "是否確認完成?"):
            for item_id in selected:
                values = self.error_status_tree.item(item_id, "values")
                if len(values) >= 3 and values[2] == "待處理":
                    new_values = list(values)
                    new_values[2] = "已處理"
                    self.error_status_tree.item(item_id, values=new_values, tags=("已處理",))

    # ------------------------------------------------
    # (3) 員工登記分頁
    # ------------------------------------------------
    def create_employee_tab(self, parent):
        left_frame = tk.Frame(parent, bg="#2B2B2B", width=600)
        left_frame.pack(side="left", fill="both", expand=True)
        right_frame = tk.Frame(parent, bg="#2B2B2B", width=600)
        right_frame.pack(side="right", fill="both", expand=True)

        emp_preview_frame = tk.LabelFrame(left_frame, text="預覽",
                                          font=("Microsoft JhengHei", 15, "bold"),
                                          bg="#2B2B2B", fg="white")
        emp_preview_frame.pack(padx=10, pady=10, fill="both", expand=True)

        self.emp_video_path = r"C:\\Users\\Yu Shan\\Downloads\\0309_ 使用 Clipchamp 製作.mp4"
        self.cap_employee = cv2.VideoCapture(self.emp_video_path)
        self.emp_video_fps = int(self.cap_employee.get(cv2.CAP_PROP_FPS))
        if self.emp_video_fps <= 0:
            self.emp_video_fps = 30

        self.emp_video_label = tk.Label(emp_preview_frame, bg="#2B2B2B")
        self.emp_video_label.pack(padx=10, pady=10)
        self.update_employee_video()

        capture_btn = ttk.Button(emp_preview_frame, text="拍攝並登記", style="Custom.TButton",
                                 command=self.capture_and_register_employee)
        capture_btn.pack(pady=5)

        self.emp_photo_label = tk.Label(emp_preview_frame,
                                        text="尚未拍攝照片",
                                        bd=2, relief="groove",
                                        width=200, height=150,
                                        bg="#2B2B2B", fg="white")
        self.emp_photo_label.pack(pady=5)

        op_frame = tk.LabelFrame(right_frame, text="手動登記",
                                 font=("Microsoft JhengHei", 14, "bold"),
                                 bg="#2B2B2B", fg="white")
        op_frame.pack(padx=10, pady=10, fill="x")

        manual_frame = tk.Frame(op_frame, bg="#2B2B2B")
        manual_frame.pack(pady=5)

        tk.Label(manual_frame, text="請輸入姓名:", font=("Microsoft JhengHei", 12, "bold"),
                 bg="#2B2B2B", fg="white").pack(side="left")
        self.manual_name_entry = tk.Entry(manual_frame, font=("Microsoft JhengHei", 12, "bold"), bg="#2B2B2B", fg="white")
        self.manual_name_entry.pack(side="left", padx=5)

        manual_btn = ttk.Button(manual_frame, text="登記",style="Custom.TButton",
                                command=lambda: self.register_employee(mode="手動"))
        manual_btn.pack(side="left", padx=5)

        search_frame = tk.Frame(right_frame, bg="#2B2B2B")
        search_frame.pack(padx=10, pady=5, fill="x")

        tk.Label(search_frame, text="搜尋姓名:",
                 font=("Microsoft JhengHei", 12, "bold"),
                 bg="#2B2B2B", fg="white").pack(side="left")
        self.search_entry = tk.Entry(search_frame, font=("Microsoft JhengHei", 12, "bold"), bg="#2B2B2B", fg="white")
        self.search_entry.pack(side="left", padx=5)
        search_btn = ttk.Button(search_frame, text="搜尋", style="Custom.TButton",
                                command=self.search_employee)
        search_btn.pack(side="left", padx=5)
        reset_btn = ttk.Button(search_frame, text="取消", style="Custom.TButton",
                               command=self.reset_employee_search)
        reset_btn.pack(side="left", padx=5)

        record_frame = tk.LabelFrame(right_frame, text="登記列表",
                                     font=("Microsoft JhengHei", 14, "bold"),
                                     bg="#2B2B2B", fg="white")
        record_frame.pack(padx=10, pady=10, fill="both", expand=True)

        self.emp_record_tree = ttk.Treeview(
            record_frame, columns=("編號", "姓名", "登記時間", "方式"),
            show="headings", height=10
        )
        self.emp_record_tree.heading("編號", text="編號")
        self.emp_record_tree.heading("姓名", text="姓名")
        self.emp_record_tree.heading("登記時間", text="登記時間")
        self.emp_record_tree.heading("方式", text="方式")
        self.emp_record_tree.column("編號", width=80, anchor="center")
        self.emp_record_tree.column("姓名", width=150, anchor="center")
        self.emp_record_tree.column("登記時間", width=100, anchor="center")
        self.emp_record_tree.column("方式", width=100, anchor="center")
        self.emp_record_tree.pack(side="left", fill="both", expand=True,
                                  padx=5, pady=5)

        record_scrollbar = tk.Scrollbar(record_frame, orient="vertical",
                                        command=self.emp_record_tree.yview, bg="#2B2B2B")
        record_scrollbar.pack(side="right", fill="y")
        self.emp_record_tree.config(yscrollcommand=record_scrollbar.set)

        self.emp_record_tree.bind("<Double-1>", self.show_employee_details)

    def update_employee_video(self):
        ret, frame = self.cap_employee.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = cv2.resize(frame, (300, 200))
            image = Image.fromarray(frame)
            self.emp_video = ImageTk.PhotoImage(image)
            self.emp_video_label.configure(image=self.emp_video)
        else:
            self.cap_employee.set(cv2.CAP_PROP_POS_FRAMES, 0)

        delay_emp = int(1000 / self.emp_video_fps)
        self.emp_video_label.after(delay_emp, self.update_employee_video)

    def capture_employee_photo(self):
        ret, frame = self.cap_employee.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = cv2.resize(frame, (250, 200))
            image = Image.fromarray(frame)
            photo = ImageTk.PhotoImage(image)
            self.emp_photo_label.configure(image=photo, text="")
            self.emp_photo_label.image = photo
            return photo
        else:
            messagebox.showwarning("警告", "無法拍攝照片！")
            return None

    def recognize_name_from_photo(self, photo):
        """留空，可自行實作人臉辨識"""
        return ""

    def capture_and_register_employee(self):
        photo = self.capture_employee_photo()
        if photo:
            recognized_name = self.recognize_name_from_photo(photo)
            current_time = self.get_current_time()
            emp_id = len(self.all_emp_records) + 1
            self.emp_photos[emp_id] = photo

            if recognized_name:
                record = (emp_id, recognized_name, current_time, "自動")
            else:
                record = (emp_id, f"未辨識_{emp_id}", current_time, "自動")

            self.all_emp_records.append(record)
            self.emp_record_tree.insert("", "end", values=record)

    def register_employee(self, mode="自動"):
        if mode == "自動":
            self.capture_and_register_employee()
        else:
            name = self.manual_name_entry.get().strip()
            if not name:
                messagebox.showwarning("警告", "請輸入姓名。")
                return
            current_time = self.get_current_time()
            emp_id = len(self.all_emp_records) + 1

            photo = self.capture_employee_photo()
            if photo:
                self.emp_photos[emp_id] = photo

            record = (emp_id, name, current_time, "手動")
            self.all_emp_records.append(record)
            self.emp_record_tree.insert("", "end", values=record)
            self.manual_name_entry.delete(0, tk.END)
            messagebox.showinfo("成功", "手動登記成功！")

    def search_employee(self):
        keyword = self.search_entry.get().strip().lower()
        for child in self.emp_record_tree.get_children():
            self.emp_record_tree.delete(child)
        filtered = [rec for rec in self.all_emp_records if keyword in rec[1].lower()]
        for rec in filtered:
            self.emp_record_tree.insert("", "end", values=rec)

    def reset_employee_search(self):
        self.search_entry.delete(0, tk.END)
        for child in self.emp_record_tree.get_children():
            self.emp_record_tree.delete(child)
        for rec in self.all_emp_records:
            self.emp_record_tree.insert("", "end", values=rec)

    def show_employee_details(self, event):
        selected = self.emp_record_tree.selection()
        if not selected:
            return
        item_id = selected[0]
        record = self.emp_record_tree.item(item_id, "values")
        if not record:
            return

        detail_win = tk.Toplevel(self.root)
        detail_win.title("員工詳細資訊")
        detail_win.geometry("500x400")
        detail_win.configure(bg="#2B2B2B")

        container = tk.Frame(detail_win, bg="#2B2B2B")
        container.pack(padx=10, pady=10, fill="x")

        tk.Label(container, text="編號：", font=("Microsoft JhengHei", 14),
                 bg="#2B2B2B", fg="white").grid(row=0, column=0, sticky="w", pady=5)
        tk.Label(container, text=record[0], font=("Microsoft JhengHei", 14),
                 bg="#2B2B2B", fg="white").grid(row=0, column=1, sticky="w", pady=5)

        tk.Label(container, text="姓名：", font=("Microsoft JhengHei", 14),
                 bg="#2B2B2B", fg="white").grid(row=1, column=0, sticky="w", pady=5)
        tk.Label(container, text=record[1], font=("Microsoft JhengHei", 14),
                 bg="#2B2B2B", fg="white").grid(row=1, column=1, sticky="w", pady=5)

        tk.Label(container, text="登記時間：", font=("Microsoft JhengHei", 14),
                 bg="#2B2B2B", fg="white").grid(row=2, column=0, sticky="w", pady=5)
        tk.Label(container, text=record[2], font=("Microsoft JhengHei", 14),
                 bg="#2B2B2B", fg="white").grid(row=2, column=1, sticky="w", pady=5)

        tk.Label(container, text="登記方式：", font=("Microsoft JhengHei", 14),
                 bg="#2B2B2B", fg="white").grid(row=3, column=0, sticky="w", pady=5)
        tk.Label(container, text=record[3], font=("Microsoft JhengHei", 14),
                 bg="#2B2B2B", fg="white").grid(row=3, column=1, sticky="w", pady=5)

        if int(record[0]) in self.emp_photos:
            tk.Label(container, text="拍攝照片：", font=("Microsoft JhengHei", 14),
                     bg="#2B2B2B", fg="white").grid(row=4, column=0, sticky="w", pady=5)
            photo_label = tk.Label(container, image=self.emp_photos[int(record[0])],
                                   bg="#2B2B2B")
            photo_label.image = self.emp_photos[int(record[0])]
            photo_label.grid(row=4, column=1, sticky="w", pady=5)
        else:
            tk.Label(container, text="無拍攝照片", font=("Microsoft JhengHei", 14),
                     bg="#2B2B2B", fg="white").grid(row=4, column=0, columnspan=2, sticky="w", pady=5)

    def get_current_time(self):
        return time.strftime("%H:%M:%S")


    # ------------------------------------------------
    # (4) 變數分頁
    # ------------------------------------------------
    def create_debug_tab(self, parent):
        self.debug_vars = []
        self.debug_labels = {}
        self.debug_update_interval = 1000  # 預設每秒更新一次

        top_frame = tk.Frame(parent, bg="#2B2B2B")
        top_frame.pack(fill="x", pady=10, padx=10)

        tk.Label(top_frame, text="輸入變數名：", font=("Microsoft JhengHei", 12),
                 bg="#2B2B2B", fg="white").pack(side="left")

        self.debug_var_entry = tk.Entry(top_frame, font=("Microsoft JhengHei", 12), bg="#2B2B2B", fg="white")
        self.debug_var_entry.pack(side="left", padx=5)

        add_btn = ttk.Button(top_frame, text="加入觀察", style="Custom.TButton", command=self.add_debug_var)
        add_btn.pack(side="left", padx=5)

        clear_btn = ttk.Button(top_frame, text="清除全部", style="Custom.TButton", command=self.clear_debug_vars)
        clear_btn.pack(side="left", padx=5)

        interval_label = tk.Label(top_frame, text="更新頻率(秒)：", font=("Microsoft JhengHei", 12), bg="#2B2B2B",
                                  fg="white")
        interval_label.pack(side="left", padx=(20, 2))

        self.debug_interval_spin = tk.Spinbox(top_frame, from_=0.5, to=10.0, increment=0.5,
                                              font=("Microsoft JhengHei", 12), width=5, bg="#2B2B2B", fg="white",
                                              command=self.update_debug_interval)
        self.debug_interval_spin.delete(0, "end")
        self.debug_interval_spin.insert(0, "1.0")
        self.debug_interval_spin.pack(side="left")

        # 常用變數快捷列
        shortcut_frame = tk.Frame(parent, bg="#2B2B2B")
        shortcut_frame.pack(fill="x", padx=10)

        common_vars = ["current_box", "box_in_B", "last_picked_label", "current_state",
                       "hand_enter_count", "hand_out_count", "current_box_left", "current_box_right"]

        for var in common_vars:
            btn = ttk.Button(shortcut_frame, text=var, style="Custom.TButton",
                             command=lambda v=var: self.add_debug_var_from_button(v))
            btn.pack(side="left", padx=3, pady=3)

        # Scrollable 區域
        canvas = tk.Canvas(parent, bg="#2B2B2B", highlightthickness=0)
        scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        self.debug_list_frame = tk.Frame(canvas, bg="#2B2B2B")

        self.debug_list_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=self.debug_list_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        scrollbar.pack(side="right", fill="y")

        self.update_debug_vars()

    def create_error_list_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        self.error_status_tree = ttk.Treeview(
            parent, columns=("編號", "類型", "狀態", "時間"),
            show="headings", height=18
        )
        self.error_status_tree.heading("編號", text="編號")
        self.error_status_tree.heading("類型", text="類型")
        self.error_status_tree.heading("狀態", text="狀態")
        self.error_status_tree.heading("時間", text="時間")
        self.error_status_tree.column("編號", width=60, anchor="center")
        self.error_status_tree.column("類型", width=200, anchor="center")
        self.error_status_tree.column("狀態", width=80, anchor="center")
        self.error_status_tree.column("時間", width=100, anchor="center")
        self.error_status_tree.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        es_scrollbar = tk.Scrollbar(parent, orient="vertical", command=self.error_status_tree.yview)
        es_scrollbar.grid(row=0, column=1, sticky="ns")
        self.error_status_tree.configure(yscrollcommand=es_scrollbar.set)

        self.error_status_tree.tag_configure("待處理", background="#990000", foreground="white")
        self.error_status_tree.tag_configure("已處理", background="#006600", foreground="white")
        self.error_status_tree.bind("<Double-Button-1>", self.complete_selected_error)

    def add_debug_var(self):
        var_name = self.debug_var_entry.get().strip()
        if var_name and var_name not in self.debug_vars:
            self.debug_vars.append(var_name)
            label = tk.Label(self.debug_list_frame, text=f"{var_name}: (載入中...)",
                             font=("Microsoft JhengHei", 12), bg="#2B2B2B", fg="white", anchor="w")
            label.pack(fill="x", pady=2)
            self.debug_labels[var_name] = label
            self.debug_var_entry.delete(0, tk.END)

    def add_debug_var_from_button(self, var_name):
        self.debug_var_entry.delete(0, tk.END)
        self.debug_var_entry.insert(0, var_name)
        self.add_debug_var()

    def clear_debug_vars(self):
        self.debug_vars.clear()
        for label in self.debug_labels.values():
            label.destroy()
        self.debug_labels.clear()

    def update_debug_vars(self):
        for var_name in self.debug_vars:
            try:
                val = eval(f"self.{var_name}")
            except Exception as e:
                val = f"無法讀取 ({e})"
            self.debug_labels[var_name].config(text=f"{var_name}: {val}")
        self.root.after(int(self.debug_update_interval), self.update_debug_vars)

    def update_debug_interval(self):
        try:
            interval = float(self.debug_interval_spin.get())
            self.debug_update_interval = int(interval * 1000)
        except:
            pass

    # =============================================
    # (5) 設定頁面
    # =============================================
    def create_settings_tab(self, parent):
        settings_frame = tk.Frame(parent, bg="#2B2B2B")
        settings_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.video_source_var = tk.StringVar(value="local")
        # ========== 模型路徑設定 ==========
        model_frame = tk.LabelFrame(settings_frame, text="模型路徑設定", font=("Microsoft JhengHei", 13, "bold"),
                                    bg="#2B2B2B", fg="white")
        model_frame.pack(fill="x", pady=5)

        tk.Label(model_frame, text="YOLO 模型路徑：", bg="#2B2B2B", fg="white").grid(row=0, column=0, padx=5, pady=5,
                                                                                    sticky="e")
        ttk.Button(model_frame, text="選擇檔案", style="Custom.TButton",command=self.browse_yolo_model).grid(row=0, column=2, padx=5)
        self.yolo_model_entry = tk.Entry(model_frame, width=60)
        self.yolo_model_entry.insert(0, self.OBJECT_MODEL_PATH)
        self.yolo_model_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        tk.Label(model_frame, text="Pose 模型路徑：", bg="#2B2B2B", fg="white").grid(row=1, column=0, padx=5, pady=5,
                                                                                    sticky="e")
        ttk.Button(model_frame, text="選擇檔案", style="Custom.TButton",command=self.browse_pose_model).grid(row=1, column=2, padx=5)
        self.pose_model_entry = tk.Entry(model_frame, width=60)
        self.pose_model_entry.insert(0, self.POSE_MODEL_PATH)
        self.pose_model_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        # ========== 影片來源選擇 ==========
        # 先定義 LabelFrame
        video_src_frame = tk.LabelFrame(settings_frame, text="影片來源選擇", font=("Microsoft JhengHei", 13, "bold"),
                                        bg="#2B2B2B", fg="white")
        video_src_frame.pack(fill="x", pady=5)
        # 加入「選擇影片」按鈕（預設 local 顯示）
        # RTSP 串流輸入欄位（預設隱藏，當選 stream 時才顯示）
        self.rtsp_frame = tk.Frame(settings_frame, bg="#2B2B2B")
        self.rtsp_frame.pack(fill="x", pady=5)

        tk.Label(self.rtsp_frame, text="RTSP 串流網址：", bg="#2B2B2B", fg="white").pack(side="left", padx=10)
        self.rtsp_url_var = tk.StringVar(value=self.camera_url)
        self.rtsp_entry = tk.Entry(self.rtsp_frame, textvariable=self.rtsp_url_var, width=60)
        self.rtsp_entry.pack(side="left", padx=5)

        # 預設先隱藏
        self.rtsp_frame.pack_forget()
        self.video_select_btn = ttk.Button(video_src_frame, text="選擇影片", style="Custom.TButton",command=self.browse_video_file)
        self.video_select_btn.pack(side="left", padx=10)

        # 判斷初始是否要顯示按鈕
        if self.video_source_var.get() != "local":
            self.video_select_btn.pack_forget()
        # 再放入影片來源選單
        tk.Label(video_src_frame, text="影片來源：", bg="#2B2B2B", fg="white").pack(side="left", padx=10, pady=5)

        video_source_combo = ttk.Combobox(video_src_frame, textvariable=self.video_source_var,
                                          values=["local", "stream", "usb"],  # <== 加了 "usb"
                                          state="readonly", width=20)
        video_source_combo.pack(side="left", padx=5)
        video_source_combo.bind("<<ComboboxSelected>>", self.on_video_source_change)


        # ========== 顯示尺寸設定 ==========
        size_frame = tk.LabelFrame(settings_frame, text="影片顯示尺寸", font=("Microsoft JhengHei", 13, "bold"),
                                   bg="#2B2B2B", fg="white")
        size_frame.pack(fill="x", pady=5)

        tk.Label(size_frame, text="寬度(px)：", bg="#2B2B2B", fg="white").grid(row=0, column=0, padx=5, pady=5)
        self.video_width_var = tk.IntVar(value=600)
        tk.Entry(size_frame, textvariable=self.video_width_var, width=10).grid(row=0, column=1, padx=5, pady=5)

        tk.Label(size_frame, text="高度(px)：", bg="#2B2B2B", fg="white").grid(row=0, column=2, padx=5, pady=5)
        self.video_height_var = tk.IntVar(value=400)
        tk.Entry(size_frame, textvariable=self.video_height_var, width=10).grid(row=0, column=3, padx=5, pady=5)
        # 橫向容器：Pose 區＋線條預覽區
        pose_and_line_container = tk.Frame(settings_frame, bg="#2B2B2B")
        pose_and_line_container.pack(fill="x", pady=5)

        # 左：Pose 判定設定
        pose_area_frame = tk.LabelFrame(pose_and_line_container, text="Pose 判定區設定 (中心為關鍵點)",
                                        font=("Microsoft JhengHei", 13, "bold"), bg="#2B2B2B", fg="white")
        pose_area_frame.pack(side="left", fill="both", expand=True, padx=5)

        tk.Label(pose_area_frame, text="框寬度(px)：", bg="#2B2B2B", fg="white").grid(row=0, column=0, padx=5, pady=5)
        self.pose_area_w_var = tk.IntVar(value=80)
        tk.Entry(pose_area_frame, textvariable=self.pose_area_w_var, width=10).grid(row=0, column=1, padx=5, pady=5)

        tk.Label(pose_area_frame, text="框高度(px)：", bg="#2B2B2B", fg="white").grid(row=0, column=2, padx=5, pady=5)
        self.pose_area_h_var = tk.IntVar(value=80)
        tk.Entry(pose_area_frame, textvariable=self.pose_area_h_var, width=10).grid(row=0, column=3, padx=5, pady=5)

        self.pose_preview_canvas = tk.Canvas(pose_area_frame, width=200, height=200, bg="#1E1E1E")
        self.pose_preview_canvas.grid(row=0, column=4, rowspan=2, padx=10, pady=5)
        self.update_pose_preview()

        self.pose_area_w_var.trace_add("write", lambda *args: self.update_pose_preview())
        self.pose_area_h_var.trace_add("write", lambda *args: self.update_pose_preview())

        # 右：偵測線預覽設定
        line_preview_frame = tk.LabelFrame(pose_and_line_container, text="偵測線示意圖",
                                           font=("Microsoft JhengHei", 13, "bold"), bg="#2B2B2B", fg="white")
        line_preview_frame.pack(side="left", fill="both", expand=True, padx=5)

        self.line_preview_canvas = tk.Canvas(line_preview_frame, width=200, height=200, bg="#000000")
        self.line_preview_canvas.pack(padx=10, pady=10)
        mode_frame = tk.Frame(line_preview_frame, bg="#2B2B2B")
        mode_frame.pack()
        tk.Label(mode_frame, text="模式：", bg="#2B2B2B", fg="white").pack(side="left")
        self.line_preview_mode_var = tk.StringVar(value="Y")
        tk.Radiobutton(mode_frame, text="Y", variable=self.line_preview_mode_var, value="Y",
                       command=lambda: self.set_line_mode("Y"), bg="#2B2B2B", fg="white", selectcolor="#2B2B2B").pack(
            side="left")
        tk.Radiobutton(mode_frame, text="X", variable=self.line_preview_mode_var, value="X",
                       command=lambda: self.set_line_mode("X"), bg="#2B2B2B", fg="white", selectcolor="#2B2B2B").pack(
            side="left")

        # 模式切換與數值
        self.line_preview_mode = tk.StringVar(value="Y")  # ⬅️ 加這行！

        mode_frame = tk.Frame(line_preview_frame, bg="#2B2B2B")
        mode_frame.pack(pady=2)

        # 閾值輸入
        threshold_frame = tk.Frame(line_preview_frame, bg="#2B2B2B")
        threshold_frame.pack(pady=2)

        tk.Label(threshold_frame, text="閾值：", bg="#2B2B2B", fg="white").pack(side="left")
        self.y_threshold_var = tk.IntVar(value=self.pose_y_threshold)
        tk.Spinbox(threshold_frame, from_=0, to=1000, width=5,
                   textvariable=self.y_threshold_var).pack(side="left", padx=5)

        self.y_threshold_var.trace_add("write", lambda *args: self.update_line_preview())

    def set_line_mode(self, mode):
        self.line_preview_mode = mode
        self.update_line_preview()

    def update_pose_preview(self):
        self.pose_preview_canvas.delete("all")
        try:
            w = self.pose_area_w_var.get()
            h = self.pose_area_h_var.get()
        except tk.TclError:
            return  # 使用者正在編輯框框還沒輸入完成，不畫 preview
        w = self.pose_area_w_var.get()
        h = self.pose_area_h_var.get()
        cx, cy = 100, 100
        self.pose_preview_canvas.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, fill="red")
        self.pose_preview_canvas.create_rectangle(cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2, outline="lime",
                                                  width=2)

    def update_line_preview(self):
        if not self.cap or not self.cap.isOpened():
            return

        ret, frame = self.cap.read()
        if not ret:
            return

        try:
            thres_val = self.y_threshold_var.get() if self.line_preview_mode_var.get() == "Y" else self.x_threshold_var.get()
        except tk.TclError:
            return  # 🛡️ 使用者輸入還沒完成（可能還是空的），先跳過不畫

        h_frame, w_frame = frame.shape[:2]
        canvas_size = 200
        scale = min(canvas_size / w_frame, canvas_size / h_frame)
        new_w = int(w_frame * scale)
        new_h = int(h_frame * scale)

        resized = cv2.resize(frame, (new_w, new_h))
        canvas_img = np.zeros((canvas_size, canvas_size, 3), dtype=np.uint8)
        offset_x = (canvas_size - new_w) // 2
        offset_y = (canvas_size - new_h) // 2
        canvas_img[offset_y:offset_y + new_h, offset_x:offset_x + new_w] = resized

        # 根據模式畫線
        mode = self.line_preview_mode_var.get()
        if mode == "Y":
            line_y = int(thres_val * scale) + offset_y
            cv2.line(canvas_img, (0, line_y), (canvas_size, line_y), (0, 255, 255), 2)
            cv2.arrowedLine(canvas_img, (canvas_size - 20, line_y - 20), (canvas_size - 20, line_y + 10), (0, 255, 255),
                            2)
            cv2.putText(canvas_img, f"Y={int(thres_val)}", (10, line_y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (0, 255, 255), 1)
        else:  # X 模式
            line_x = int(thres_val * scale) + offset_x
            cv2.line(canvas_img, (line_x, 0), (line_x, canvas_size), (0, 255, 255), 2)
            cv2.arrowedLine(canvas_img, (line_x - 20, 20), (line_x + 10, 20), (0, 255, 255), 2)
            cv2.putText(canvas_img, f"X={int(thres_val)}", (line_x + 5, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (0, 255, 255), 1)

        img_rgb = cv2.cvtColor(canvas_img, cv2.COLOR_BGR2RGB)
        img_pil = Image.fromarray(img_rgb)
        self.line_preview_image = ImageTk.PhotoImage(img_pil)
        self.line_preview_canvas.create_image(0, 0, anchor="nw", image=self.line_preview_image)

    def browse_yolo_model(self):
        path = filedialog.askopenfilename(filetypes=[("YOLO Model Files", "*.pt"), ("All Files", "*.*")])
        if path:
            self.yolo_model_entry.delete(0, tk.END)
            self.yolo_model_entry.insert(0, path)

    def browse_pose_model(self):
        path = filedialog.askopenfilename(filetypes=[("Pose Model Files", "*.pt"), ("All Files", "*.*")])
        if path:
            self.pose_model_entry.delete(0, tk.END)
            self.pose_model_entry.insert(0, path)

    def browse_video_file(self):
        path = filedialog.askopenfilename(filetypes=[("Video Files", "*.mp4 *.avi *.mov"), ("All Files", "*.*")])
        if path:
            self.video_path = path
            messagebox.showinfo("影片已選擇", f"目前影片來源已更新為：\n{path}")

    def on_video_source_change(self, event=None):
        if self.video_source_var.get() == "local":
            self.video_select_btn.pack(side="left", padx=10)
            self.rtsp_frame.pack_forget()
        else:
            self.video_select_btn.pack_forget()
            self.rtsp_frame.pack(fill="x", pady=5)


    #=====================LLM=====================
    # 補上 create_analysis_tab 方法：
    def create_analysis_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        parent.rowconfigure(1, weight=0)

        # 聊天歷史區（用 Text + Scrollbar，readonly）
        chat_frame = tk.Frame(parent, bg="#1E1E1E")
        chat_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        self.chat_history = tk.Text(
            chat_frame, height=13, wrap="word", bg="#1E1E1E", fg="white",
            font=("Microsoft JhengHei", 11), state="disabled"
        )
        self.chat_history.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.chat_scrollbar = tk.Scrollbar(chat_frame, command=self.chat_history.yview)
        self.chat_history.config(yscrollcommand=self.chat_scrollbar.set)
        self.chat_scrollbar.pack(side="right", fill="y")

        # 下半部 輸入 + 按鈕
        input_frame = tk.Frame(parent, bg="#2B2B2B")
        input_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 10))
        input_frame.columnconfigure(0, weight=1)

        self.manual_question_entry = tk.Entry(
            input_frame, font=("Microsoft JhengHei", 12), width=80
        )
        self.manual_question_entry.grid(row=0, column=0, sticky="ew", padx=10, pady=2)
        self.manual_question_entry.bind("<Return>", lambda e: self.send_chat_message())

        ask_btn = ttk.Button(input_frame, text="送出", style="Custom.TButton",
                             command=self.send_chat_message)
        ask_btn.grid(row=0, column=1, padx=10, pady=2)

    def send_chat_message(self):
        msg = self.manual_question_entry.get().strip()
        if not msg:
            messagebox.showwarning("提醒", "請先輸入內容")
            return
        self.manual_question_entry.delete(0, tk.END)

        # ➊ 只在这里插入用户消息
        self.append_chat_message("user", msg)

        # ➋ 再把提问发给后台线程，不要再在后台重复 append user
        threading.Thread(target=self.ask_gpt_in_background,args=(msg,),daemon=True).start()


    def send_manual_question_to_gpt(self):
        question = self.manual_question_entry.get().strip()
        if not question:
            messagebox.showwarning(title="提醒", message="請先輸入你要問的內容！")
            return
        threading.Thread(target=self.ask_gpt_in_background, args=(question,), daemon=True).start()

    def _archive_reply(self, text: str) -> None:
        """
        把 user 的輸入和 GPT 回覆存到 logs/gpt_history.txt。
        """
        try:
            os.makedirs("logs", exist_ok=True)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open("logs/gpt_history.txt", "a", encoding="utf-8") as f:
                f.write(f"[{now}]\n")
                # 上一次 user 話存在 chat_messages 倒數第二筆
                last_user = next(
                    (m["content"] for m in reversed(self.chat_messages) if m["role"] == "user"),
                    "<unknown>"
                )
                f.write(f"User: {last_user}\n")
                f.write(f"Assistant: {text}\n")
                f.write("-" * 5 + "\n")
        except Exception as e:
            # 失敗就寫到 console，避免影響主流程
            print("⚠️ 寫入 GPT 歷史檔失敗：", e)

    def ask_gpt_in_background(self, question: str):
        """改用 ChatCompletion stream，保留旗標與自動跟進邏輯"""
        # 先把 user 話加入 history
        self.chat_messages.append({"role": "user", "content": question})


        def run_chat():
            try:
                # ① 開始呼叫 GPT streaming
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    stream=True,
                    messages=self.chat_messages,
                )

                # ② 逐 chunk 顯示
                full_reply = ""
                self.append_chat_message("gpt", "")  # 在 UI 裡先開個空白段落
                for chunk in response:
                    delta = chunk.choices[0].delta
                    content = getattr(delta, "content", "")
                    if content:
                        full_reply += content
                        # 每拿到一小段就更新 UI
                        self.append_chat_message("gpt", content, stream_update=True)

                # ③ 完整回覆拿到後，做 flag 注入
                reply = full_reply
                flags = ["NEED_RECENT_DATA", "NEED_ERP_DATA", "NEED_LINE_RT_DATA"]
                if not any(reply.startswith(f) for f in flags):
                    low = reply.lower()
                    if "最近" in low and "分鐘" in low:
                        reply = "NEED_RECENT_DATA " + reply
                    elif "erp" in low:
                        reply = "NEED_ERP_DATA " + reply
                    elif "即時" in low:
                        reply = "NEED_LINE_RT_DATA " + reply

                # ④ 處理 flag
                loader_map = {
                    "NEED_RECENT_DATA": self._load_recent_log,
                    "NEED_ERP_DATA": self._load_erp_data,
                    "NEED_LINE_RT_DATA": self._load_line_rt,
                }
                for flag, loader in loader_map.items():
                    if reply.startswith(flag):
                        follow_up = reply[len(flag):].lstrip()
                        extra_ctx = loader()
                        # 把這次回覆也加入 history
                        self.chat_messages.append({"role": "assistant", "content": reply})
                        return self._send_followup(follow_up, extra_ctx)

                # ⑤ 正常結束：把 assistant 的完整回覆蓋回 history，再存檔
                self.chat_messages.append({"role": "assistant", "content": reply})
                self._archive_reply(reply)

            except Exception as e:
                messagebox.showerror("錯誤", f"Assistant 回覆失敗：\n{e}")

        threading.Thread(target=run_chat, daemon=True).start()

    def append_chat_message(self, role, msg, stream_update=False):
        """
        stream_update=True 时只在最后一行追加内容，
        否则在用户消息前插入前缀并换行。
        """
        self.chat_history.config(state="normal")

        if role == "user":
            # 用户消息前加「👤 您：」
            prefix = "\n  👤 您："
            # 新段落
            self.chat_history.insert(tk.END, prefix, ("bold", "role_user"))
            self.chat_history.insert(tk.END, msg + "\n\n", ("msg_user",))
        else:
            # 助手新段落
            if not stream_update:
                self.chat_history.insert(tk.END, "\n  🤖 LLM：", ("bold", "role_gpt"))
            # 直接插入流式或完整回复文本
            self.chat_history.insert(tk.END, msg, ("msg_gpt",))

        self.chat_history.see(tk.END)
        self.chat_history.config(state="disabled")

    def ask_followup_chat(self, question: str, context_text: str):
        """有旗標時自動把 context + user 問句，再次 stream"""
        self.chat_messages.append({"role": "user", "content": context_text + "\n\n" + question})
        def run_follow():
            resp = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=self.chat_messages,
                stream=True
            )
            reply_parts = []
            for chunk in resp:
                part = chunk.choices[0].delta.get("content", "")
                reply_parts.append(part)
                self.append_chat_stream(part)
            final = "".join(reply_parts)
            self.chat_messages.append({"role": "assistant", "content": final})
            self._archive_reply(final)

        threading.Thread(target=run_follow, daemon=True).start()

    def display_gpt_reply(self, reply):
        self.chat_history.config(state="normal")
        self.chat_history.delete("1.0", "end")
        self.chat_history.insert("1.0", reply)
        self.chat_history.config(state="disabled")

    def _send_followup(self, question: str, context_text: str):
        # 先把 extra context + question 丟進 history
        if context_text is None:
            context_text = ""
        prompt = context_text + "\n\n" + question
        self.chat_messages.append({"role": "user", "content": prompt})
        self.append_chat_message("user", question)

        # 重複走 streaming chat completion
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=self.chat_messages,
            stream=True
        )

        full = ""
        self.append_chat_message("gpt", "", stream_update=False)
        for chunk in response:
            c = getattr(chunk.choices[0].delta, "content", "")
            full += c
            self.append_chat_message("gpt", c, stream_update=True)

        # 存檔 & 加入 history
        self.chat_messages.append({"role": "assistant", "content": full})
        self._archive_reply(full)

    # ────────────────────────────────
    # 產線 / ERP / 最近 5 分鐘資料的暫時實作
    # ────────────────────────────────
    def _load_recent_log(self) -> str:
        """
        回傳最近 5 分鐘內的完整 JSONL raw data，
        讓 GPT 在追問時能讀到所有細節。
        """
        try:
            if not self.recent_5min_records:
                return "(最近 5 分鐘內沒有任何紀錄。)"
            lines = [json.dumps(rec, ensure_ascii=False) for rec in self.recent_5min_records]
            jsonl_content = "\n".join(lines)
            return (
                "以下是最近 5 分鐘的生產狀態原始 JSONL 資料：\n"
                "```jsonl\n"
                f"{jsonl_content}\n"
                "```\n"
            )
        except Exception as e:
            return f"(讀取最近紀錄失敗：{e})"

    def _load_erp_data(self) -> str:
        """
        從 ERP 撈單 / 品質 / 庫存…先用假資料。
        """
        return "(ERP 資料尚未串接，請忽略)"

    def _load_line_rt(self) -> str:
        """
        產線即時資料（PLC / 感測器）─ 先回傳空字串。
        """
        return "(產線即時資料尚未串接)"

    def record_frame_info(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        emp = self.all_emp_records[-1][1] if self.all_emp_records else "未知"
        frame_data = {
            "timestamp": now,
            "confidence_threshold": self.confidence_threshold.get(),
            "current_state": self.current_state,
            "current_box": self.current_box,
            "box_in_B": self.box_in_B,
            "hand_enter_count": self.hand_enter_count,
            "hand_out_count": self.hand_out_count,
            "last_picked_label": self.last_picked_label,
            "current_step_index": self.current_step_index,
            "total_completed": self.total_completed,
            "total_errors": self.total_errors,
            "emp_id": emp
        }
        self.frame_buffer.append(frame_data)
        self.append_status_record(frame_data)  # ← 加這行，每秒都塞進 deque 裡

    def save_frame_buffer(self):
        # 把當前狀態記錄到 in-memory 的 deque（recent_5min_records）中
        self.record_frame_info()
        # 1 秒後再呼叫自己
        self.root.after(1000, self.save_frame_buffer)

    def call_gpt_analysis(self):
        try:
            result = subprocess.run(["python", "Analyze_With_Gpt.py"], capture_output=True, text=True)
            result_str = result.stdout.strip()

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.update_gpt_analysis_result(result_str, now_str)

            # 可選：也跳一個彈窗確認
            messagebox.showinfo("分析完成", "已根據歷史數據更新分析結果")
        except Exception as e:
            messagebox.showerror("錯誤", f"呼叫 GPT 分析失敗：{e}")



    def save_current_status(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        emp = self.all_emp_records[-1][1] if self.all_emp_records else "未知"
        data = {
            "timestamp": now,
            "confidence_threshold": self.confidence_threshold.get(),
            "current_state": self.current_state,
            "current_box": self.current_box,
            "box_in_B": self.box_in_B,
            "hand_enter_count": self.hand_enter_count,
            "hand_out_count": self.hand_out_count,
            "last_picked_label": self.last_picked_label,
            "current_step_index": self.current_step_index,
            "total_completed": self.total_completed,
            "total_errors": self.total_errors,
            "emp_id": emp
        }

        os.makedirs("logs", exist_ok=True)  # 🔥 補上
        with open("logs/current_status.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        self.root.after(5000, self.save_current_status)  # 再排下一輪

    def save_historical_status(self):
        now = datetime.now()
        filename = now.strftime("logs/%Y-%m-%d-%H-%M.json")
        emp = self.all_emp_records[-1][1] if self.all_emp_records else "未知"
        data = {
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "confidence_threshold": self.confidence_threshold.get(),
            "current_state": self.current_state,
            "current_box": self.current_box,
            "box_in_B": self.box_in_B,
            "hand_enter_count": self.hand_enter_count,
            "hand_out_count": self.hand_out_count,
            "last_picked_label": self.last_picked_label,
            "current_step_index": self.current_step_index,
            "total_completed": self.total_completed,
            "total_errors": self.total_errors,
            "emp_id": emp
        }

        os.makedirs("logs", exist_ok=True)  # 🔥 這裡也補上
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        self.root.after(600000, self.save_historical_status)
        self.call_gpt_analysis()
    def update_gpt_analysis_result(self, content, timestamp):
        if hasattr(self, "gpt_suggestion_label") and self.gpt_suggestion_label.winfo_exists():
            self.gpt_suggestion_label.config(text=f"（根據 {timestamp} 分析）")

        if hasattr(self, "gpt_analysis_text") and self.gpt_analysis_text.winfo_exists():
            self.gpt_analysis_text.config(state="normal")
            self.gpt_analysis_text.delete("1.0", tk.END)

            self.gpt_analysis_text.config(state="disabled")
            try:
                content = content.encode("utf-8", errors="replace").decode("utf-8")  # 🧠 強制處理編碼
                safe_insert(self.gpt_analysis_text, content)
            except Exception as e:
                messagebox.showerror("錯誤", f"⚠️ 顯示回覆失敗：{e}")

    def periodic_half_hour_save(self):
        self.save_half_hour_jsonl()
        self.root.after(1800000, self.periodic_half_hour_save)  # 再排一次

    def append_status_record(self, data):
        self.recent_5min_records.append(data)

    def save_half_hour_jsonl(self):
        os.makedirs("logs/jsonl", exist_ok=True)
        now = datetime.now()
        filename = f"logs/jsonl/half_hour_{now.strftime('%Y-%m-%d-%H-%M')}.jsonl"
        with open(filename, "w", encoding="utf-8") as f:
            for record in self.recent_5min_records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        for file in glob.glob("logs/jsonl/session-*.jsonl"):
            os.remove(file)



def safe_insert(text_widget, content):
    """
    安全地將 content 插入到 Text 元件中，處理編碼問題避免 'ascii codec' 錯誤。
    """
    try:
        # 嘗試用 UTF-8 強制編碼處理非 ASCII 字元
        content = content.encode("utf-8", errors="replace").decode("utf-8")
        text_widget.insert("1.0", content)
    except Exception as e:
        messagebox.showerror("錯誤", f"⚠ 顯示回覆失敗：{e}")


def _update_detection_result(self, result):
    if result is not None:
        self.latest_detection = result


def main():
    locale.setlocale(locale.LC_ALL, '')
    root = tk.Tk()
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    root.option_add("*Background", "#2B2B2B")
    root.option_add("*Foreground", "white")
    app = TestSystemUI(root)
    root.mainloop()

def _thread_err_hook(args):
    print("### 執行緒例外 ###")
    traceback.print_exception(args.exc_type, args.exc_value, args.exc_traceback,
                              file=sys.stdout)

threading.excepthook = _thread_err_hook


if __name__ == "__main__":
    main()
