import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from tkinter.scrolledtext import ScrolledText
from PIL import Image, ImageTk
from pygments import lex
from pygments.lexers import CLexer
from pygments.styles import get_style_by_name
from flowchart_generator import generate_flowchart, update_global_settings, global_settings
import os
import shutil
import cairosvg

class FlowchartApp:
    def __init__(self, root):
        self.root = root
        self.root.title("БА-20 Щурко А.В. Генератор блок-схем (кваліфікаційна робота бакалавра)")
        self.create_widgets()
        self.create_menu()
        self.scale_factor = 1.0  # Коефіцієнт масштабування
        self.image = None  # Зберігання оригінального зображення
        self.style = get_style_by_name("default")  # Використання стандартного стилю
        self.setup_tags()
        self.auto_update = True  # Автоматичне оновлення блок-схеми
        self.update_id = None  # ID запланованого оновлення

    # Створення віджетів
    def create_widgets(self):
        # Створення фреймів
        self.settings_frame = ttk.Frame(self.root, padding="10")
        self.settings_frame.grid(row=0, column=0, sticky="ns")
        self.editor_frame = ttk.Frame(self.root, padding="10")
        self.editor_frame.grid(row=0, column=1, sticky="nsew")
        self.output_frame = ttk.Frame(self.root, padding="10")
        self.output_frame.grid(row=0, column=2, sticky="nsew", rowspan=2)

        # Фрейм налаштувань
        ttk.Label(self.settings_frame, text="Налаштування", font=("Arial", 14, "bold")).grid(row=0, column=0, pady=10)
        self.create_spinbox("Розмір шрифту в блоці", "node_fontsize", 1, 1, 64)
        self.create_spinbox("Розмір шрифту на лінії", "edge_fontsize", 2, 1, 64)
        self.create_spinbox("Розмір шрифту заголовку", "cluster_fontsize", 3, 1, 64)
        self.create_spinbox("Товщина ліній", "edge_penwidth", 9, 0, 10, increment=0.1)
        self.create_spinbox("Товщина контурів блоків", "node_penwidth", 10, 0, 10, increment=0.1)
        self.create_spinbox("Відступ", "cluster_margin", 11, 0, 100)
        self.create_spinbox("Кількість символів в рядку", "width_factor", 13, 1, 64)
        self.create_checkbox("Онлайн-режим", "online_mode", 16)
        self.create_checkbox("Стрілки на лініях", "edge_arrows", 17, "normal", "none",initial=True)
        self.create_checkbox("Стрілки циклу", "loopback_arrows", 18, "normal", "none",initial=True)
        self.create_checkbox("Авто-оновлення", "auto_update", 19, initial=True)

        # Додавання кнопки генерації блок-схеми
        self.generate_button = ttk.Button(self.settings_frame, text="Згенерувати блок-схему", command=self.generate_flowchart)
        self.generate_button.grid(row=20, column=0, columnspan=2, pady=10)

        # Фрейм редактора
        ttk.Label(self.editor_frame, text="Вхідний код", font=("Arial", 14, "bold")).grid(row=0, column=0, pady=10)
        self.input_text = ScrolledText(self.editor_frame, width=80, height=15, font=("Consolas", 12), wrap=tk.WORD)
        self.input_text.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        self.input_text.bind("<<Modified>>", self.on_input_modified)
        self.input_text.bind("<Button-3>", self.show_input_context_menu)

        # Фрейм виводу
        ttk.Label(self.output_frame, text="Перегляд блок-схеми", font=("Arial", 14, "bold")).grid(row=0, column=0, pady=10)

        # Полотно та прокрутка для зображення
        self.canvas = tk.Canvas(self.output_frame, background="white", width=800, height=600)
        self.canvas.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        self.scroll_y = tk.Scrollbar(self.output_frame, orient="vertical", command=self.canvas.yview)
        self.scroll_y.grid(row=1, column=1, sticky="ns")
        self.scroll_x = tk.Scrollbar(self.output_frame, orient="horizontal", command=self.canvas.xview)
        self.scroll_x.grid(row=2, column=0, sticky="ew")
        self.canvas.configure(yscrollcommand=self.scroll_y.set, xscrollcommand=self.scroll_x.set)
        self.canvas.bind("<Button-3>", self.show_canvas_context_menu)

        # Прив'язка подій миші для перетягування та масштабування
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.canvas.bind("<Configure>", self.on_resize)

        # Налаштування ваг рядків/стовпців для зміни розміру
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_columnconfigure(2, weight=1)
        self.output_frame.grid_rowconfigure(1, weight=1)
        self.output_frame.grid_columnconfigure(0, weight=1)
        self.editor_frame.grid_rowconfigure(1, weight=1)
        self.editor_frame.grid_columnconfigure(0, weight=1)

  # Створення меню
    def create_menu(self):
        menu_bar = tk.Menu(self.root)
        self.root.config(menu=menu_bar)
        file_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(label="Відкрити", command=self.load_file)
        file_menu.add_command(label="Зберегти як...", command=self.save_as)
        file_menu.add_command(label="Вийти", command=self.root.quit)
        export_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Експортувати", menu=export_menu)
        export_menu.add_command(label="Зберегти AST", command=self.save_ast)
        export_menu.add_command(label="Зберегти DOT", command=self.save_dot)

    # Створення spinbox
    def create_spinbox(self, label, setting_name, row, from_, to_, increment=1):
        ttk.Label(self.settings_frame, text=label).grid(row=row, column=0, sticky="w", pady=5)
        spinbox = ttk.Spinbox(self.settings_frame, from_=from_, to=to_, increment=increment, width=5,
                              command=lambda: self.schedule_update(setting_name, spinbox.get()))
        spinbox.set(global_settings[setting_name])
        spinbox.grid(row=row, column=1, pady=5)

    # Створення checkbox
    def create_checkbox(self, label, setting_name, row, true_value="True", false_value="False", initial=False):
        var = tk.BooleanVar(value=global_settings[setting_name] == true_value if initial is None else initial)
        checkbox = ttk.Checkbutton(self.settings_frame, text=label, variable=var,
                                   command=lambda: self.update_setting(setting_name, true_value if var.get() else false_value))
        checkbox.grid(row=row, column=0, columnspan=2, sticky="w", pady=5)
        if setting_name == "auto_update":
            var.trace_add("write", self.update_auto_update)

    # Оновлення налаштувань
    def update_setting(self, setting_name, value):
        if setting_name in ["online_mode", "edge_arrows", "loopback_arrows", "auto_update"]:
            value = bool(value) if value in [True, False] else value
        else:
            value = float(value) if "." in str(value) else int(value)
        update_global_settings({setting_name: value})
        if self.auto_update:
            self.schedule_update()

    # Планування оновлення з затримкою
    def schedule_update(self, setting_name=None, value=None):
        if setting_name:
            self.update_setting(setting_name, value)
        if self.update_id:
            self.root.after_cancel(self.update_id)
        self.update_id = self.root.after(250, self.generate_flowchart)

    # Оновлення автоматичного оновлення
    def update_auto_update(self, *args):
        self.auto_update = global_settings["auto_update"]
        if self.auto_update:
            self.generate_flowchart()

    # Завантаження файлу
    def load_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("C files", "*.c"), ("All files", "*.*")])
        if file_path:
            with open(file_path, 'r', encoding='utf-8') as file:
                self.input_text.delete(1.0, tk.END)
                self.input_text.insert(tk.END, file.read())
            self.highlight_text()
            self.generate_flowchart()

    # Генерація блок-схеми
    def generate_flowchart(self):
        c_code = self.input_text.get(1.0, tk.END)
        dot_output, image_path = generate_flowchart(c_code)
        self.display_image(image_path)

    # Збереження як
    def save_as(self):
        filetypes = [('PNG files', '*.png'), ('SVG files', '*.svg'), ('JPG files', '*.jpg'), ('PDF files', '*.pdf'), ('DOT files', '*.dot'), ('All files', '*.*')]
        file_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=filetypes)
        if file_path:
            self.save_flowchart(os.path.splitext(file_path)[-1][1:], file_path)

    # Збереження AST
    def save_ast(self):
        self.save_file('ast.txt', 'AST')

    # Збереження DOT
    def save_dot(self):
        self.save_file('flowchart.dot', 'DOT')

    # Збереження файлу
    def save_file(self, temp_filename, file_label):
        temp_dir = os.path.join(os.getcwd(), 'temp')
        temp_file_path = os.path.join(temp_dir, temp_filename)
        if not os.path.exists(temp_file_path):
            messagebox.showerror("Помилка", f"Не знайдено файл {file_label} для зберігання")
            return
        file_path = filedialog.asksaveasfilename(defaultextension=f".{temp_filename.split('.')[-1]}", filetypes=[(f'{file_label} files', f'*.{temp_filename.split(".")[-1]}'), ('All files', '*.*')])
        if file_path:
            shutil.copy(temp_file_path, file_path)
            messagebox.showinfo("Успіх", f"Файл {file_label} збережено успішно.")

    # Збереження блок-схеми
    def save_flowchart(self, format, file_path=None):
        temp_dir = os.path.join(os.getcwd(), 'temp')
        temp_file_path = os.path.join(temp_dir, 'flowchart.svg')
        if not os.path.exists(temp_file_path):
            messagebox.showerror("Помилка", f"Не знайдено SVG файл для збереження.")
            return
        if not file_path:
            file_path = filedialog.asksaveasfilename(defaultextension=f".{format}", filetypes=[(f'{format.upper()} files', f'*.{format}'), ('All files', '*.*')])
        if file_path:
            try:
                if format == 'jpg':
                    png_path = temp_file_path.replace(".svg", ".png")
                    cairosvg.svg2png(url=temp_file_path, write_to=png_path)
                    image = Image.open(png_path)
                    image = image.convert('RGB')
                    image.save(file_path, 'JPEG')
                elif format == 'pdf':
                    pdf_path = temp_file_path.replace(".svg", ".pdf")
                    cairosvg.svg2pdf(url=temp_file_path, write_to=pdf_path)
                    shutil.copy(pdf_path, file_path)
                elif format == 'png':
                    png_path = temp_file_path.replace(".svg", ".png")
                    cairosvg.svg2png(url=temp_file_path, write_to=png_path)
                    shutil.copy(png_path, file_path)
                else:
                    shutil.copy(temp_file_path, file_path)
                messagebox.showinfo("Успіх", f"Файл {format.upper()} збережено успішно.")
            except Exception as e:
                messagebox.showerror("Помилка", f"Не вдалося зберегти {format.upper()} файл: {e}")

    # Відображення зображення
    def display_image(self, image_path):
        if image_path.endswith(".svg"):
            png_path = image_path.replace(".svg", ".png")
            cairosvg.svg2png(url=image_path, write_to=png_path)
            image_path = png_path

        self.image = Image.open(image_path)
        self.update_canvas_image(center_image=True)

    # Оновлення зображення на полотні
    def update_canvas_image(self, center_image=False):
        if self.image is None:
            return
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        # Розрахунок нового розміру із збереженням співвідношення сторін
        img_width, img_height = self.image.size
        scale_factor = min(canvas_width / img_width, canvas_height / img_height) * self.scale_factor

        new_width = int(img_width * scale_factor)
        new_height = int(img_height * scale_factor)

        resized_image = self.image.resize((new_width, new_height), Image.LANCZOS)

        self.photo = ImageTk.PhotoImage(resized_image)
        self.canvas.delete("all")
        
        x_offset = (canvas_width - new_width) // 2
        y_offset = (canvas_height - new_height) // 2
        self.canvas.create_image(x_offset, y_offset, anchor="nw", image=self.photo)
        
        self.canvas.image = self.photo
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

    # Обробка натискання кнопки
    def on_button_press(self, event):
        self.canvas.scan_mark(event.x, event.y)

    # Обробка перетягування
    def on_drag(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    # Обробка масштабування
    def on_zoom(self, event):
        if event.delta > 0:
            self.scale_factor *= 1.1
        elif event.delta < 0:
            self.scale_factor *= 0.9

        self.update_canvas_image()

    # Обробка зміни розміру вікна
    def on_resize(self, event):
        self.update_canvas_image()

    # Обробка зміни введення
    def on_input_modified(self, event):
        self.input_text.edit_modified(False)
        self.highlight_text()
        self.schedule_update()

    # Налаштування тегів для підсвічування
    def setup_tags(self):
        for token, style in self.style:
            foreground = style['color']
            if foreground:
                self.input_text.tag_configure(str(token), foreground="#" + foreground)

    # Підсвічування тексту коду
    def highlight_text(self):
        c_code = self.input_text.get("1.0", tk.END)
        self.input_text.mark_set("range_start", "1.0")
        for token, content in lex(c_code, CLexer()):
            self.input_text.mark_set("range_end", "range_start + %dc" % len(content))
            self.input_text.tag_add(str(token), "range_start", "range_end")
            self.input_text.mark_set("range_start", "range_end")

    # Показ контекстного меню для введення
    def show_input_context_menu(self, event):
        self.create_context_menu(event, self.input_text)

    # Показ контекстного меню для полотна
    def show_canvas_context_menu(self, event):
        context_menu = tk.Menu(self.root, tearoff=0)
        context_menu.add_command(label="Зберегти як...", command=self.save_as)
        context_menu.add_command(label="Скинути приближення", command=self.reset_zoom)
        context_menu.add_command(label="Очистити", command=self.clear_canvas)
        context_menu.post(event.x_root, event.y_root)

    # Створення контекстного меню
    def create_context_menu(self, event, text_widget):
        context_menu = tk.Menu(self.root, tearoff=0)
        context_menu.add_command(label="Вирізати", command=lambda: text_widget.event_generate("<<Cut>>"))
        context_menu.add_command(label="Копіювати", command=lambda: text_widget.event_generate("<<Copy>>"))
        context_menu.add_command(label="Вставити", command=lambda: text_widget.event_generate("<<Paste>>"))
        context_menu.add_command(label="Видалити", command=lambda: text_widget.delete("sel.first", "sel.last"))
        context_menu.add_separator()
        context_menu.add_command(label="Очистити", command=lambda: text_widget.delete(1.0, tk.END))
        context_menu.post(event.x_root, event.y_root)

    # Скидання масштабу
    def reset_zoom(self):
        self.scale_factor = 1.0
        self.update_canvas_image(center_image=True)

    # Очищення полотна
    def clear_canvas(self):
        self.canvas.delete("all")

if __name__ == "__main__":
    root = tk.Tk()
    app = FlowchartApp(root)
    root.mainloop()
