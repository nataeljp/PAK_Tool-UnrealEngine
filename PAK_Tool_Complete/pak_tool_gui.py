#!/usr/bin/env python3
"""
PAK Tool GUI v3 - Aplicação Desktop Avançada para gerenciar arquivos .pak do Unreal Engine
Funcionalidades: Visualização, Edição, Reempacotamento, Adicionar, Substituir, Deletar (estilo 7-Zip)
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
import os
import json
from pyuepak import PakFile
import threading
import tempfile
import io

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class TextEditorWindow:
    """Janela de editor de texto para arquivos .ini e outros"""
    def __init__(self, parent, file_path, content, on_save_callback=None):
        self.window = tk.Toplevel(parent)
        self.window.title(f"Editor - {Path(file_path).name}")
        self.window.geometry("900x700")
        
        self.file_path = file_path
        self.original_content = content
        self.on_save_callback = on_save_callback
        self.modified = False
        
        self.create_widgets()
        self.load_content()
        
    def create_widgets(self):
        """Criar widgets do editor"""
        # Frame principal
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Barra de ferramentas
        toolbar = ttk.Frame(main_frame)
        toolbar.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(toolbar, text="💾 Salvar", command=self.save_content).grid(row=0, column=0, padx=5)
        ttk.Button(toolbar, text="🔄 Reverter", command=self.revert_content).grid(row=0, column=1, padx=5)
        ttk.Button(toolbar, text="❌ Fechar", command=self.close_window).grid(row=0, column=2, padx=5)
        
        self.status_label = ttk.Label(toolbar, text="")
        self.status_label.grid(row=0, column=3, padx=20)
        
        # Área de texto
        text_frame = ttk.Frame(main_frame)
        text_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        
        self.text_widget = scrolledtext.ScrolledText(
            text_frame, 
            wrap=tk.NONE, 
            font=("Consolas", 10),
            undo=True,
            maxundo=-1
        )
        self.text_widget.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Scrollbar horizontal
        h_scrollbar = ttk.Scrollbar(text_frame, orient=tk.HORIZONTAL, command=self.text_widget.xview)
        self.text_widget.configure(xscrollcommand=h_scrollbar.set)
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # Detectar modificações
        self.text_widget.bind('<<Modified>>', self.on_text_modified)
        
        # Atalhos de teclado
        self.window.bind('<Control-s>', lambda e: self.save_content())
        self.window.bind('<Control-z>', lambda e: self.text_widget.edit_undo())
        self.window.bind('<Control-y>', lambda e: self.text_widget.edit_redo())
        
    def load_content(self):
        """Carregar conteúdo no editor"""
        try:
            # Tentar decodificar como texto
            if isinstance(self.original_content, bytes):
                text = self.original_content.decode('utf-8', errors='replace')
            else:
                text = self.original_content
            
            self.text_widget.insert(1.0, text)
            self.text_widget.edit_modified(False)
            self.modified = False
            
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao carregar conteúdo:\n{str(e)}")
            self.window.destroy()
    
    def on_text_modified(self, event=None):
        """Callback quando texto é modificado"""
        if self.text_widget.edit_modified():
            self.modified = True
            self.window.title(f"Editor - {Path(self.file_path).name} *")
            self.status_label.config(text="Modificado", foreground="orange")
            self.text_widget.edit_modified(False)
    
    def save_content(self):
        """Salvar conteúdo editado"""
        if not self.modified:
            messagebox.showinfo("Informação", "Nenhuma modificação para salvar")
            return
        
        content = self.text_widget.get(1.0, tk.END)
        
        if self.on_save_callback:
            success = self.on_save_callback(self.file_path, content.encode('utf-8'))
            if success:
                self.modified = False
                self.window.title(f"Editor - {Path(self.file_path).name}")
                self.status_label.config(text="✓ Salvo", foreground="green")
                messagebox.showinfo("Sucesso", "Arquivo salvo! Use 'Salvar PAK Como' para aplicar as mudanças.")
        else:
            messagebox.showwarning("Aviso", "Função de salvamento não disponível")
    
    def revert_content(self):
        """Reverter para conteúdo original"""
        if self.modified:
            result = messagebox.askyesno("Confirmar", "Descartar todas as modificações?")
            if result:
                self.text_widget.delete(1.0, tk.END)
                self.load_content()
    
    def close_window(self):
        """Fechar janela"""
        if self.modified:
            result = messagebox.askyesnocancel(
                "Salvar alterações?",
                "Há modificações não salvas. Deseja salvá-las?"
            )
            if result is None:  # Cancel
                return
            elif result:  # Yes
                self.save_content()
        
        self.window.destroy()


class ImageViewerWindow:
    """Janela de visualização de imagens (incluindo DDS)"""
    def __init__(self, parent, file_path, image_data):
        self.window = tk.Toplevel(parent)
        self.window.title(f"Visualizador - {Path(file_path).name}")
        self.window.geometry("800x600")
        
        self.file_path = file_path
        self.image_data = image_data
        
        self.create_widgets()
        self.load_image()
    
    def create_widgets(self):
        """Criar widgets do visualizador"""
        # Frame principal
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Barra de ferramentas
        toolbar = ttk.Frame(main_frame)
        toolbar.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(toolbar, text="💾 Salvar Como", command=self.save_image).grid(row=0, column=0, padx=5)
        ttk.Button(toolbar, text="❌ Fechar", command=self.window.destroy).grid(row=0, column=1, padx=5)
        
        self.info_label = ttk.Label(toolbar, text="")
        self.info_label.grid(row=0, column=2, padx=20)
        
        # Canvas para imagem
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)
        
        self.canvas = tk.Canvas(canvas_frame, bg='#2a2a2a')
        self.canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        h_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))
    
    def load_image(self):
        """Carregar e exibir imagem"""
        if not PIL_AVAILABLE:
            messagebox.showerror("Erro", "Biblioteca PIL/Pillow não disponível.\nInstale com: pip install Pillow")
            self.window.destroy()
            return
        
        try:
            # Tentar carregar imagem
            image = Image.open(io.BytesIO(self.image_data))
            
            # Informações
            self.info_label.config(text=f"{image.format} | {image.width}x{image.height} | {image.mode}")
            
            # Converter para PhotoImage
            self.photo = ImageTk.PhotoImage(image)
            
            # Exibir no canvas
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
            self.canvas.config(scrollregion=(0, 0, image.width, image.height))
            
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao carregar imagem:\n{str(e)}\n\nFormato DDS pode não ser suportado.")
            self.window.destroy()
    
    def save_image(self):
        """Salvar imagem"""
        output_path = filedialog.asksaveasfilename(
            title="Salvar imagem como",
            initialfile=Path(self.file_path).name,
            defaultextension=Path(self.file_path).suffix,
            filetypes=[
                ("PNG", "*.png"),
                ("JPEG", "*.jpg"),
                ("BMP", "*.bmp"),
                ("Todos", "*.*")
            ]
        )
        
        if output_path:
            try:
                with open(output_path, 'wb') as f:
                    f.write(self.image_data)
                messagebox.showinfo("Sucesso", f"Imagem salva:\n{output_path}")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao salvar:\n{str(e)}")


class PakToolGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("PAK Tool v3 - Unreal Engine PAK Manager")
        self.root.geometry("1200x800")
        self.root.minsize(900, 600)
        
        # Variáveis
        self.current_pak_path = None
        self.current_pak = None
        self.pak_files_list = []
        self.modified_files = {}  # Arquivos modificados: {path: content}
        self.added_files = {}  # Arquivos adicionados: {path: content}
        self.deleted_files = set()  # Arquivos deletados
        
        # Configurar estilo
        self.setup_style()
        
        # Criar interface
        self.create_widgets()
        
    def setup_style(self):
        """Configurar estilo da aplicação"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Cores
        bg_color = "#1a1a1a"
        fg_color = "#ffffff"
        accent_color = "#2ecc71"
        
        style.configure(".", background=bg_color, foreground=fg_color)
        style.configure("TFrame", background=bg_color)
        style.configure("TLabel", background=bg_color, foreground=fg_color, font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("TButton", font=("Segoe UI", 10), padding=10)
        style.map("TButton", background=[("active", accent_color)])
        
        self.root.configure(bg=bg_color)
        
    def create_widgets(self):
        """Criar widgets da interface"""
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # Título
        title_label = ttk.Label(main_frame, text="🎮 PAK Tool v3 - Unreal Engine", style="Title.TLabel")
        title_label.grid(row=0, column=0, pady=(0, 20))
        
        # Frame de controles
        controls_frame = ttk.Frame(main_frame)
        controls_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 20))
        controls_frame.columnconfigure(1, weight=1)
        
        # Botões
        ttk.Button(controls_frame, text="📂 Abrir .PAK", command=self.open_pak_file).grid(row=0, column=0, padx=(0, 10))
        
        self.file_label = ttk.Label(controls_frame, text="Nenhum arquivo carregado", foreground="#888888")
        self.file_label.grid(row=0, column=1, sticky=tk.W, padx=10)
        
        ttk.Button(controls_frame, text="ℹ️ Info", command=self.show_info).grid(row=0, column=2, padx=5)
        ttk.Button(controls_frame, text="📤 Extrair Tudo", command=self.extract_all).grid(row=0, column=3, padx=5)
        ttk.Button(controls_frame, text="💾 Salvar PAK Como", command=self.save_pak_as).grid(row=0, column=4, padx=5)
        ttk.Button(controls_frame, text="📦 Novo PAK", command=self.create_pak_from_folder).grid(row=0, column=5, padx=5)
        
        # Notebook (abas)
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Aba 1: Lista de arquivos
        files_frame = ttk.Frame(self.notebook)
        self.notebook.add(files_frame, text="📁 Arquivos")
        
        files_frame.columnconfigure(0, weight=1)
        files_frame.rowconfigure(1, weight=1)
        
        # Barra de busca e botões
        search_frame = ttk.Frame(files_frame)
        search_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        search_frame.columnconfigure(1, weight=1)
        
        ttk.Label(search_frame, text="🔍 Buscar:").grid(row=0, column=0, padx=(0, 10))
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_files)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        # Botões de gerenciamento
        ttk.Button(search_frame, text="➕ Adicionar", command=self.add_files_to_pak).grid(row=0, column=2, padx=5)
        ttk.Button(search_frame, text="🔄 Substituir", command=self.replace_file_in_pak).grid(row=0, column=3, padx=5)
        ttk.Button(search_frame, text="🗑️ Deletar", command=self.delete_file_from_pak).grid(row=0, column=4, padx=5)
        
        # Treeview para arquivos
        tree_frame = ttk.Frame(files_frame)
        tree_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        
        self.files_tree = ttk.Treeview(tree_frame, columns=("type", "size", "status"), show="tree headings")
        self.files_tree.heading("#0", text="Arquivo")
        self.files_tree.heading("type", text="Tipo")
        self.files_tree.heading("size", text="Tamanho")
        self.files_tree.heading("status", text="Status")
        self.files_tree.column("#0", width=450)
        self.files_tree.column("type", width=80)
        self.files_tree.column("size", width=100)
        self.files_tree.column("status", width=100)
        
        # Configurar cores da treeview
        style = ttk.Style()
        style.configure("Treeview", background="white", foreground="black", fieldbackground="white")
        style.map("Treeview", background=[("selected", "#0078d7")], foreground=[("selected", "white")])
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.files_tree.yview)
        self.files_tree.configure(yscrollcommand=scrollbar.set)
        
        self.files_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Menu de contexto
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="👁️ Visualizar", command=self.view_file_content)
        self.context_menu.add_command(label="✏️ Editar", command=self.edit_file_content)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="🔄 Substituir", command=self.replace_file_in_pak)
        self.context_menu.add_command(label="🗑️ Deletar", command=self.delete_file_from_pak)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="📤 Extrair", command=self.extract_selected_file)
        self.context_menu.add_command(label="📋 Copiar caminho", command=self.copy_file_path)
        
        self.files_tree.bind("<Button-3>", self.show_context_menu)
        self.files_tree.bind("<Double-1>", lambda e: self.view_file_content())
        self.files_tree.bind("<Delete>", lambda e: self.delete_file_from_pak())
        
        # Aba 2: Informações
        info_frame = ttk.Frame(self.notebook)
        self.notebook.add(info_frame, text="ℹ️ Informações")
        
        info_frame.columnconfigure(0, weight=1)
        info_frame.rowconfigure(0, weight=1)
        
        self.info_text = scrolledtext.ScrolledText(info_frame, wrap=tk.WORD, font=("Consolas", 10))
        self.info_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)
        self.info_text.config(state=tk.DISABLED)
        
        # Aba 3: Log
        log_frame = ttk.Frame(self.notebook)
        self.notebook.add(log_frame, text="📋 Log")
        
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, font=("Consolas", 9))
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)
        self.log_text.config(state=tk.DISABLED)
        
        # Barra de status
        self.status_var = tk.StringVar(value="Pronto")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        
        self.log("✨ PAK Tool v3 - Gerenciamento Completo Estilo 7-Zip")
        self.log("📂 Abra um arquivo .pak ou crie um novo")
        self.log("➕ Adicione, substitua, delete e edite arquivos diretamente")
        
    def log(self, message):
        """Adicionar mensagem ao log"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        
    def open_pak_file(self):
        """Abrir arquivo .pak"""
        file_path = filedialog.askopenfilename(
            title="Selecione um arquivo .pak",
            filetypes=[("PAK files", "*.pak"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
        
        self.status_var.set("Carregando arquivo...")
        self.log(f"Abrindo arquivo: {file_path}")
        
        # Carregar em thread separada para não travar a interface
        thread = threading.Thread(target=self.load_pak_file, args=(file_path,))
        thread.daemon = True
        thread.start()
        
    def load_pak_file(self, file_path):
        """Carregar arquivo .pak (executado em thread separada)"""
        try:
            pak = PakFile()
            pak.read(file_path)
            
            self.current_pak_path = file_path
            self.current_pak = pak
            self.modified_files = {}  # Limpar modificações
            self.added_files = {}  # Limpar adições
            self.deleted_files = set()  # Limpar deleções
            
            # Atualizar interface na thread principal
            self.root.after(0, self.update_interface_after_load)
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Erro", f"Erro ao carregar arquivo:\n{str(e)}"))
            self.root.after(0, lambda: self.status_var.set("Erro ao carregar arquivo"))
            self.log(f"ERRO: {str(e)}")
            
    def update_interface_after_load(self):
        """Atualizar interface após carregar arquivo"""
        filename = Path(self.current_pak_path).name
        self.file_label.config(text=filename, foreground="#2ecc71")
        self.status_var.set(f"Arquivo carregado: {filename}")
        self.log(f"✓ Arquivo carregado com sucesso: {self.current_pak.count} arquivos encontrados")
        
        # Listar arquivos
        self.list_pak_contents()
        
        # Mostrar informações
        self.show_info()
        
    def get_file_status(self, file_path):
        """Obter status do arquivo"""
        if file_path in self.deleted_files:
            return "🗑️ Deletado"
        elif file_path in self.added_files:
            return "➕ Novo"
        elif file_path in self.modified_files:
            return "✏️ Modificado"
        else:
            return ""
    
    def list_pak_contents(self):
        """Listar conteúdo do arquivo .pak"""
        if not self.current_pak:
            return
        
        # Limpar árvore
        for item in self.files_tree.get_children():
            self.files_tree.delete(item)
        
        # Obter lista de arquivos (incluindo adicionados, excluindo deletados)
        self.pak_files_list = self.current_pak.list_files()
        all_files = set(self.pak_files_list) | set(self.added_files.keys())
        all_files -= self.deleted_files
        
        # Organizar por tipo
        by_type = {}
        for file_path in all_files:
            ext = Path(file_path).suffix or "sem extensão"
            if ext not in by_type:
                by_type[ext] = []
            by_type[ext].append(file_path)
        
        # Adicionar à árvore
        for ext in sorted(by_type.keys()):
            parent = self.files_tree.insert("", tk.END, text=f"{ext} ({len(by_type[ext])} arquivos)", 
                                           values=("Pasta", "", ""), open=False)
            
            for file_path in sorted(by_type[ext]):
                status = self.get_file_status(file_path)
                self.files_tree.insert(parent, tk.END, text=file_path, 
                                      values=(ext, "", status), tags=(file_path,))
        
        self.log(f"Listados {len(all_files)} arquivos")
        
    def filter_files(self, *args):
        """Filtrar arquivos na árvore"""
        if not self.current_pak:
            return
        
        search_term = self.search_var.get().lower()
        
        # Limpar árvore
        for item in self.files_tree.get_children():
            self.files_tree.delete(item)
        
        if not search_term:
            self.list_pak_contents()
            return
        
        # Obter todos os arquivos
        all_files = set(self.pak_files_list) | set(self.added_files.keys())
        all_files -= self.deleted_files
        
        # Filtrar arquivos
        filtered = [f for f in all_files if search_term in f.lower()]
        
        # Organizar por tipo
        by_type = {}
        for file_path in filtered:
            ext = Path(file_path).suffix or "sem extensão"
            if ext not in by_type:
                by_type[ext] = []
            by_type[ext].append(file_path)
        
        # Adicionar à árvore
        for ext in sorted(by_type.keys()):
            parent = self.files_tree.insert("", tk.END, text=f"{ext} ({len(by_type[ext])} arquivos)", 
                                           values=("Pasta", "", ""), open=True)
            
            for file_path in sorted(by_type[ext]):
                status = self.get_file_status(file_path)
                self.files_tree.insert(parent, tk.END, text=file_path, 
                                      values=(ext, "", status), tags=(file_path,))
        
    def show_info(self):
        """Mostrar informações do arquivo .pak"""
        if not self.current_pak:
            messagebox.showinfo("Informação", "Nenhum arquivo .pak carregado")
            return
        
        total_files = len(set(self.pak_files_list) | set(self.added_files.keys()) - self.deleted_files)
        
        info_text = f"""
╔══════════════════════════════════════════════════════════════╗
║              INFORMAÇÕES DO ARQUIVO PAK                      ║
╚══════════════════════════════════════════════════════════════╝

📦 Arquivo: {Path(self.current_pak_path).name if self.current_pak_path else "Novo PAK"}
📏 Tamanho: {os.path.getsize(self.current_pak_path) / 1024:.2f} KB
📍 Mount Point: {self.current_pak.mount_point}
🔢 Versão: {self.current_pak.version}
📁 Total de arquivos: {total_files}
🔒 Criptografado: {'Sim' if hasattr(self.current_pak, 'encrypted') and self.current_pak.encrypted else 'Não'}

╔══════════════════════════════════════════════════════════════╗
║              MODIFICAÇÕES PENDENTES                          ║
╚══════════════════════════════════════════════════════════════╝

✏️ Arquivos modificados: {len(self.modified_files)}
➕ Arquivos adicionados: {len(self.added_files)}
🗑️ Arquivos deletados: {len(self.deleted_files)}

╔══════════════════════════════════════════════════════════════╗
║              DISTRIBUIÇÃO POR TIPO                           ║
╚══════════════════════════════════════════════════════════════╝

"""
        
        # Contar por tipo
        all_files = set(self.pak_files_list) | set(self.added_files.keys())
        all_files -= self.deleted_files
        
        by_type = {}
        for file_path in all_files:
            ext = Path(file_path).suffix or "sem extensão"
            by_type[ext] = by_type.get(ext, 0) + 1
        
        for ext, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
            info_text += f"{ext:20s} : {count:5d} arquivos\n"
        
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(1.0, info_text)
        self.info_text.config(state=tk.DISABLED)
        
        # Mudar para aba de informações
        self.notebook.select(1)
        
    def show_context_menu(self, event):
        """Mostrar menu de contexto"""
        item = self.files_tree.identify_row(event.y)
        if item:
            self.files_tree.selection_set(item)
            # Verificar se é um arquivo (tem tags)
            if self.files_tree.item(item)["tags"]:
                self.context_menu.post(event.x_root, event.y_root)
    
    def add_files_to_pak(self):
        """Adicionar arquivos ao PAK"""
        if not self.current_pak:
            messagebox.showinfo("Informação", "Abra um arquivo .pak primeiro ou crie um novo")
            return
        
        file_paths = filedialog.askopenfilenames(
            title="Selecione arquivos para adicionar",
            filetypes=[("Todos os arquivos", "*.*")]
        )
        
        if not file_paths:
            return
        
        # Perguntar caminho interno no PAK
        internal_path = tk.simpledialog.askstring(
            "Caminho Interno",
            "Digite o caminho interno no PAK (ex: Config/, Textures/, etc)\nDeixe vazio para raiz:",
            initialvalue=""
        )
        
        if internal_path is None:  # Cancelou
            return
        
        added_count = 0
        for file_path in file_paths:
            try:
                with open(file_path, 'rb') as f:
                    data = f.read()
                
                filename = Path(file_path).name
                internal_file_path = f"{internal_path}/{filename}" if internal_path else filename
                
                self.added_files[internal_file_path] = data
                added_count += 1
                self.log(f"➕ Arquivo adicionado: {internal_file_path} ({len(data)} bytes)")
                
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao adicionar {Path(file_path).name}:\n{str(e)}")
        
        if added_count > 0:
            messagebox.showinfo("Sucesso", f"{added_count} arquivo(s) adicionado(s)!\n\nUse 'Salvar PAK Como' para aplicar as mudanças.")
            self.list_pak_contents()
            self.show_info()
    
    def replace_file_in_pak(self):
        """Substituir arquivo no PAK"""
        selection = self.files_tree.selection()
        if not selection:
            messagebox.showinfo("Informação", "Selecione um arquivo para substituir")
            return
        
        item = selection[0]
        tags = self.files_tree.item(item)["tags"]
        
        if not tags:
            messagebox.showinfo("Informação", "Selecione um arquivo para substituir")
            return
        
        file_path = tags[0]
        
        # Selecionar arquivo de substituição
        new_file_path = filedialog.askopenfilename(
            title=f"Selecione arquivo para substituir: {Path(file_path).name}",
            filetypes=[("Todos os arquivos", "*.*")]
        )
        
        if not new_file_path:
            return
        
        try:
            with open(new_file_path, 'rb') as f:
                data = f.read()
            
            # Adicionar aos modificados ou adicionados
            if file_path in self.added_files:
                self.added_files[file_path] = data
            else:
                self.modified_files[file_path] = data
            
            # Remover de deletados se estava lá
            self.deleted_files.discard(file_path)
            
            self.log(f"🔄 Arquivo substituído: {file_path} ({len(data)} bytes)")
            messagebox.showinfo("Sucesso", f"Arquivo substituído!\n\nUse 'Salvar PAK Como' para aplicar as mudanças.")
            
            self.list_pak_contents()
            self.show_info()
            
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao substituir arquivo:\n{str(e)}")
    
    def delete_file_from_pak(self):
        """Deletar arquivo ou pasta do PAK"""
        selection = self.files_tree.selection()
        if not selection:
            messagebox.showinfo("Informação", "Selecione um arquivo para deletar")
            return
        
        item = selection[0]
        tags = self.files_tree.item(item)["tags"]
        item_text = self.files_tree.item(item)["text"]
        
        if not tags:
            messagebox.showinfo("Informação", "Selecione um arquivo para deletar")
            return
        
        file_path = tags[0]
        
        # Verificar se é uma pasta (extensão)
        if " (" in item_text and "arquivos)" in item_text:
            # É uma pasta - deletar todos os arquivos desta extensão
            ext = file_path  # Na verdade é a extensão
            files_to_delete = [f for f in self.pak_files_list if Path(f).suffix.lower() == ext and f not in self.deleted_files]
            
            if not files_to_delete:
                messagebox.showinfo("Informação", "Nenhum arquivo para deletar nesta pasta")
                return
            
            result = messagebox.askyesno(
                "Confirmar Deleção Múltipla",
                f"Deseja deletar TODOS os arquivos desta pasta?\n\n{item_text}\n\nTotal: {len(files_to_delete)} arquivo(s)\n\nUse 'Salvar PAK Como' para aplicar."
            )
            
            if not result:
                return
            
            # Deletar todos
            for fp in files_to_delete:
                self.deleted_files.add(fp)
                self.modified_files.pop(fp, None)
                self.added_files.pop(fp, None)
            
            self.log(f"🗑️ {len(files_to_delete)} arquivo(s) marcados para deleção")
            messagebox.showinfo("Sucesso", f"{len(files_to_delete)} arquivo(s) marcados para deleção!\n\nUse 'Salvar PAK Como' para aplicar.")
        else:
            # É um arquivo individual
            result = messagebox.askyesno(
                "Confirmar Deleção",
                f"Deletar arquivo?\n\n{file_path}\n\nEsta ação será aplicada ao salvar o PAK."
            )
            
            if not result:
                return
            
            # Adicionar aos deletados
            self.deleted_files.add(file_path)
            
            # Remover de modificados e adicionados se estava lá
            self.modified_files.pop(file_path, None)
            self.added_files.pop(file_path, None)
            
            self.log(f"🗑️ Arquivo marcado para deleção: {file_path}")
            messagebox.showinfo("Sucesso", f"Arquivo marcado para deleção!\n\nUse 'Salvar PAK Como' para aplicar as mudanças.")
        
        self.list_pak_contents()
        self.show_info()

    
    def view_file_content(self):
        """Visualizar conteúdo do arquivo"""
        selection = self.files_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        tags = self.files_tree.item(item)["tags"]
        
        if not tags:
            return
        
        file_path = tags[0]
        
        # Verificar se foi deletado
        if file_path in self.deleted_files:
            messagebox.showwarning("Aviso", "Este arquivo foi marcado para deleção")
            return
        
        ext = Path(file_path).suffix.lower()
        
        self.status_var.set(f"Carregando {Path(file_path).name}...")
        self.log(f"Visualizando: {file_path}")
        
        # Carregar em thread separada
        thread = threading.Thread(target=self.do_view_file, args=(file_path, ext))
        thread.daemon = True
        thread.start()
    
    def do_view_file(self, file_path, ext):
        """Visualizar arquivo (executado em thread separada)"""
        try:
            # Verificar de onde carregar
            if file_path in self.added_files:
                data = self.added_files[file_path]
            elif file_path in self.modified_files:
                data = self.modified_files[file_path]
            else:
                data = self.current_pak.read_file(file_path)
            
            # Decidir como visualizar baseado na extensão
            if ext in ['.txt', '.ini', '.cfg', '.log', '.xml', '.json', '.md', '.csv']:
                # Arquivo de texto - abrir editor
                self.root.after(0, lambda: TextEditorWindow(self.root, file_path, data, self.on_file_saved))
            
            elif ext in ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tga', '.dds']:
                # Imagem - abrir visualizador
                self.root.after(0, lambda: ImageViewerWindow(self.root, file_path, data))
            
            else:
                # Arquivo binário - perguntar o que fazer
                self.root.after(0, lambda: self.handle_binary_file(file_path, data))
            
            self.root.after(0, lambda: self.status_var.set("Pronto"))
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Erro", f"Erro ao visualizar arquivo:\n{str(e)}"))
            self.root.after(0, lambda: self.status_var.set("Erro ao visualizar arquivo"))
            self.log(f"ERRO: {str(e)}")
    
    def handle_binary_file(self, file_path, data):
        """Lidar com arquivo binário"""
        result = messagebox.askyesno(
            "Arquivo Binário",
            f"Este é um arquivo binário ({Path(file_path).suffix}).\n\n"
            f"Tamanho: {len(data)} bytes\n\n"
            "Deseja extrair este arquivo?"
        )
        
        if result:
            output_path = filedialog.asksaveasfilename(
                title="Salvar arquivo como",
                initialfile=Path(file_path).name,
                defaultextension=Path(file_path).suffix
            )
            
            if output_path:
                try:
                    with open(output_path, 'wb') as f:
                        f.write(data)
                    messagebox.showinfo("Sucesso", f"Arquivo extraído:\n{output_path}")
                except Exception as e:
                    messagebox.showerror("Erro", f"Erro ao salvar:\n{str(e)}")
    
    def edit_file_content(self):
        """Editar conteúdo do arquivo"""
        selection = self.files_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        tags = self.files_tree.item(item)["tags"]
        
        if not tags:
            return
        
        file_path = tags[0]
        ext = Path(file_path).suffix.lower()
        
        # Verificar se é editável
        if ext not in ['.txt', '.ini', '.cfg', '.log', '.xml', '.json', '.md', '.csv']:
            messagebox.showwarning("Aviso", f"Tipo de arquivo {ext} não é editável como texto.")
            return
        
        self.view_file_content()  # Reutilizar função de visualização
    
    def on_file_saved(self, file_path, content):
        """Callback quando arquivo é salvo no editor"""
        try:
            # Adicionar aos modificados ou adicionados
            if file_path in self.added_files:
                self.added_files[file_path] = content
            else:
                self.modified_files[file_path] = content
            
            self.log(f"✓ Arquivo modificado: {file_path} ({len(content)} bytes)")
            
            # Atualizar lista e informações
            self.list_pak_contents()
            self.show_info()
            
            return True
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao salvar modificação:\n{str(e)}")
            return False
    
    def extract_selected_file(self):
        """Extrair arquivo selecionado"""
        selection = self.files_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        tags = self.files_tree.item(item)["tags"]
        
        if not tags:
            messagebox.showinfo("Informação", "Selecione um arquivo para extrair")
            return
        
        file_path = tags[0]
        
        # Verificar se foi deletado
        if file_path in self.deleted_files:
            messagebox.showwarning("Aviso", "Este arquivo foi marcado para deleção")
            return
        
        # Selecionar pasta de destino
        output_path = filedialog.asksaveasfilename(
            title="Salvar arquivo como",
            initialfile=Path(file_path).name,
            defaultextension=Path(file_path).suffix
        )
        
        if not output_path:
            return
        
        self.status_var.set(f"Extraindo {Path(file_path).name}...")
        self.log(f"Extraindo: {file_path}")
        
        # Extrair em thread separada
        thread = threading.Thread(target=self.do_extract_file, args=(file_path, output_path))
        thread.daemon = True
        thread.start()
        
    def do_extract_file(self, file_path, output_path):
        """Extrair arquivo (executado em thread separada)"""
        try:
            # Verificar de onde carregar
            if file_path in self.added_files:
                data = self.added_files[file_path]
            elif file_path in self.modified_files:
                data = self.modified_files[file_path]
            else:
                data = self.current_pak.read_file(file_path)
            
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'wb') as f:
                f.write(data)
            
            self.root.after(0, lambda: messagebox.showinfo("Sucesso", f"Arquivo extraído:\n{output_path}"))
            self.root.after(0, lambda: self.status_var.set("Arquivo extraído com sucesso"))
            self.log(f"✓ Arquivo extraído: {output_path} ({len(data)} bytes)")
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Erro", f"Erro ao extrair arquivo:\n{str(e)}"))
            self.root.after(0, lambda: self.status_var.set("Erro ao extrair arquivo"))
            self.log(f"ERRO: {str(e)}")
            
    def copy_file_path(self):
        """Copiar caminho do arquivo para clipboard"""
        selection = self.files_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        tags = self.files_tree.item(item)["tags"]
        
        if tags:
            file_path = tags[0]
            self.root.clipboard_clear()
            self.root.clipboard_append(file_path)
            self.status_var.set(f"Caminho copiado: {file_path}")
            self.log(f"Caminho copiado: {file_path}")
        
    def extract_all(self):
        """Extrair todos os arquivos"""
        if not self.current_pak:
            messagebox.showinfo("Informação", "Nenhum arquivo .pak carregado")
            return
        
        # Obter todos os arquivos
        all_files = set(self.pak_files_list) | set(self.added_files.keys())
        all_files -= self.deleted_files
        
        # Selecionar pasta de destino
        output_dir = filedialog.askdirectory(title="Selecione a pasta de destino")
        
        if not output_dir:
            return
        
        result = messagebox.askyesno(
            "Confirmar",
            f"Extrair {len(all_files)} arquivos para:\n{output_dir}\n\nContinuar?"
        )
        
        if not result:
            return
        
        self.status_var.set(f"Extraindo {len(all_files)} arquivos...")
        self.log(f"Iniciando extração de {len(all_files)} arquivos para: {output_dir}")
        
        # Extrair em thread separada
        thread = threading.Thread(target=self.do_extract_all, args=(output_dir, list(all_files)))
        thread.daemon = True
        thread.start()
        
    def do_extract_all(self, output_dir, files_list):
        """Extrair todos os arquivos (executado em thread separada)"""
        extracted = 0
        failed = 0
        
        for file_path in files_list:
            try:
                # Verificar de onde carregar
                if file_path in self.added_files:
                    data = self.added_files[file_path]
                elif file_path in self.modified_files:
                    data = self.modified_files[file_path]
                else:
                    data = self.current_pak.read_file(file_path)
                
                output_path = Path(output_dir) / file_path.lstrip('/')
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(output_path, 'wb') as f:
                    f.write(data)
                
                extracted += 1
                self.root.after(0, lambda: self.status_var.set(f"Extraindo... {extracted}/{len(files_list)}"))
                
            except Exception as e:
                failed += 1
                self.log(f"ERRO ao extrair {file_path}: {str(e)}")
        
        self.root.after(0, lambda: messagebox.showinfo(
            "Extração Concluída",
            f"Extração concluída!\n\n✓ Extraídos: {extracted}\n✗ Falhas: {failed}\n\n📁 Destino: {output_dir}"
        ))
        self.root.after(0, lambda: self.status_var.set(f"Extração concluída: {extracted} arquivos"))
        self.log(f"✓ Extração concluída: {extracted} extraídos, {failed} falhas")
    
    def save_pak_as(self):
        """Salvar PAK com modificações"""
        if not self.current_pak:
            messagebox.showinfo("Informação", "Abra um arquivo .pak primeiro")
            return
        
        if not self.modified_files and not self.added_files and not self.deleted_files:
            messagebox.showinfo("Informação", "Nenhuma modificação para salvar.")
            return
        
        output_path = filedialog.asksaveasfilename(
            title="Salvar PAK como",
            defaultextension=".pak",
            filetypes=[("PAK files", "*.pak"), ("All files", "*.*")]
        )
        
        if not output_path:
            return
        
        self.status_var.set("Criando novo PAK...")
        self.log(f"Criando novo PAK: {output_path}")
        self.log(f"Modificações: {len(self.modified_files)} modificados, {len(self.added_files)} adicionados, {len(self.deleted_files)} deletados")
        
        # Criar em thread separada
        thread = threading.Thread(target=self.do_save_pak, args=(output_path,))
        thread.daemon = True
        thread.start()
    
    def do_save_pak(self, output_path):
        """Salvar PAK (executado em thread separada)"""
        try:
            # Criar PAK novo
            new_pak = PakFile()
            new_pak.mount_point = self.current_pak.mount_point
            new_pak.version = self.current_pak.version
            
            # Obter lista final de arquivos
            all_files = set(self.pak_files_list) | set(self.added_files.keys())
            all_files -= self.deleted_files
            
            # Adicionar todos os arquivos
            for file_path in all_files:
                # Usar versão modificada/adicionada se existir
                if file_path in self.added_files:
                    data = self.added_files[file_path]
                elif file_path in self.modified_files:
                    data = self.modified_files[file_path]
                else:
                    data = self.current_pak.read_file(file_path)
                
                # Adicionar ao novo PAK
                new_pak.add_file(file_path, data)
            
            # Salvar
            new_pak.write(output_path)
            
            self.root.after(0, lambda: messagebox.showinfo(
                "Sucesso",
                f"PAK criado com sucesso!\n\n"
                f"📦 Arquivo: {Path(output_path).name}\n"
                f"📁 Total de arquivos: {len(all_files)}\n"
                f"✏️ Modificados: {len(self.modified_files)}\n"
                f"➕ Adicionados: {len(self.added_files)}\n"
                f"🗑️ Deletados: {len(self.deleted_files)}"
            ))
            self.root.after(0, lambda: self.status_var.set("PAK criado com sucesso"))
            self.log(f"✓ PAK criado: {output_path}")
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Erro", f"Erro ao criar PAK:\n{str(e)}"))
            self.root.after(0, lambda: self.status_var.set("Erro ao criar PAK"))
            self.log(f"ERRO: {str(e)}")
    
    def create_pak_from_folder(self):
        """Criar PAK a partir de uma pasta"""
        folder_path = filedialog.askdirectory(title="Selecione a pasta com os arquivos")
        
        if not folder_path:
            return
        
        output_path = filedialog.asksaveasfilename(
            title="Salvar PAK como",
            defaultextension=".pak",
            filetypes=[("PAK files", "*.pak"), ("All files", "*.*")]
        )
        
        if not output_path:
            return
        
        self.status_var.set("Criando PAK...")
        self.log(f"Criando PAK a partir de: {folder_path}")
        
        # Criar em thread separada
        thread = threading.Thread(target=self.do_create_pak_from_folder, args=(folder_path, output_path))
        thread.daemon = True
        thread.start()
    
    def do_create_pak_from_folder(self, folder_path, output_path):
        """Criar PAK a partir de pasta (executado em thread separada)"""
        try:
            pak = PakFile()
            pak.mount_point = "../../../"
            pak.version = 9  # Versão padrão UE5
            
            folder = Path(folder_path)
            files_added = 0
            
            # Adicionar todos os arquivos da pasta
            for file_path in folder.rglob('*'):
                if file_path.is_file():
                    relative_path = file_path.relative_to(folder)
                    
                    with open(file_path, 'rb') as f:
                        data = f.read()
                    
                    pak.add_file(str(relative_path), data)
                    files_added += 1
                    
                    self.root.after(0, lambda: self.status_var.set(f"Adicionando arquivos... {files_added}"))
            
            # Salvar PAK
            pak.write(output_path)
            
            self.root.after(0, lambda: messagebox.showinfo(
                "Sucesso",
                f"PAK criado com sucesso!\n\n"
                f"📦 Arquivo: {Path(output_path).name}\n"
                f"📁 Total de arquivos: {files_added}"
            ))
            self.root.after(0, lambda: self.status_var.set("PAK criado com sucesso"))
            self.log(f"✓ PAK criado: {output_path} ({files_added} arquivos)")
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Erro", f"Erro ao criar PAK:\n{str(e)}"))
            self.root.after(0, lambda: self.status_var.set("Erro ao criar PAK"))
            self.log(f"ERRO: {str(e)}")


def main():
    root = tk.Tk()
    app = PakToolGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
