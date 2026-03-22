import os
import sys
import subprocess
# Poder usar scripts de python en linux: python3 -m venv .venv && source .venv/bin/activate
def instalar_dependencias():
    """Instala las librerías necesarias antes de importarlas."""
    # (Nombre en PIP, Nombre al importar)
    libs = [
        ("pymupdf", "fitz"), 
        ("rich", "rich"), 
        ("tqdm", "tqdm"), 
        ("readchar", "readchar"), 
        ("pikepdf", "pikepdf"),
        ("Pillow", "PIL")
    ]
    
    for lib_pip, lib_import in libs:
        try:
            __import__(lib_import)
        except ImportError:
            print(f"[*] Instalando dependencia faltante: {lib_pip}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", lib_pip])
            except Exception as e:
                print(f"[!] Error crítico instalando {lib_pip}: {e}")
                sys.exit(1)

# --- PRIMERO INSTALAMOS ---
instalar_dependencias()

# --- LUEGO IMPORTAMOS ---
import fitz
import pikepdf
import readchar
from tqdm import tqdm
from PIL import Image
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from rich.prompt import Prompt, IntPrompt

console = Console()

class PDFNinjaMaster:
    def __init__(self):
        self.entrada = "./pdfs_protegidos"
        self.salida = "./pdfs_libres"
        for d in [self.entrada, self.salida]:
            if not os.path.exists(d): os.makedirs(d)

    def abrir_y_limpiar(self, ruta_in):
        """Usa pikepdf para eliminar restricciones de seguridad."""
        try:
            with pikepdf.open(ruta_in, allow_overwriting_input=True) as pdf:
                temp_path = ruta_in + ".tmp"
                pdf.save(temp_path)
            return temp_path
        except:
            return ruta_in

    def imagenes_a_pdf(self):
        """Convierte imágenes de la carpeta de entrada en un único PDF."""
        exts = ('.png', '.jpg', '.jpeg', '.webp')
        fotos = sorted([f for f in os.listdir(self.entrada) if f.lower().endswith(exts)])
        
        if not fotos:
            console.print("[red]No hay imágenes (JPG/PNG/WEBP) en la carpeta de entrada.[/red]")
            return

        nombre_out = Prompt.ask("Nombre del PDF final", default="fotos_convertidas.pdf")
        if not nombre_out.lower().endswith(".pdf"): nombre_out += ".pdf"

        lista_imgs = []
        try:
            for foto in tqdm(fotos, desc="Procesando imágenes"):
                img = Image.open(os.path.join(self.entrada, foto)).convert("RGB")
                lista_imgs.append(img)
            
            if lista_imgs:
                primera = lista_imgs.pop(0)
                primera.save(os.path.join(self.salida, nombre_out), save_all=True, append_images=lista_imgs)
                console.print(f"[bold green]✅ Creado: {nombre_out}[/bold green]")
        except Exception as e:
            console.print(f"[red]Error en conversión: {e}[/red]")

    def unir_pdfs_interactivo(self):
        todos = sorted([f for f in os.listdir(self.entrada) if f.endswith('.pdf')])
        if not todos: return

        cola_union = []
        indice_sel = 0
        filtro = ""
        en_cola_view = False 

        with Live(self.render_ui([], [], 0, "", False), refresh_per_second=15, screen=True) as live:
            while True:
                items_mostrar = [f for f in (cola_union if en_cola_view else todos) if filtro.lower() in f.lower()]
                
                if not items_mostrar: indice_sel = 0
                elif indice_sel >= len(items_mostrar): indice_sel = len(items_mostrar) - 1

                live.update(self.render_ui(
                    [f for f in todos if filtro.lower() in f.lower()] if not en_cola_view else todos,
                    cola_union if not en_cola_view else items_mostrar,
                    indice_sel, filtro, en_cola_view
                ))
                
                key = readchar.readkey()
                if key in [readchar.key.ESC, '\x1b']: return
                if key == '\x13': # CTRL+S
                    if cola_union: break
                    continue
                if key == readchar.key.TAB:
                    en_cola_view = not en_cola_view
                    filtro = ""; indice_sel = 0
                    continue
                if key == readchar.key.UP and items_mostrar:
                    indice_sel = (indice_sel - 1) % len(items_mostrar)
                if key == readchar.key.DOWN and items_mostrar:
                    indice_sel = (indice_sel + 1) % len(items_mostrar)
                if key == readchar.key.ENTER and items_mostrar and not en_cola_view:
                    cola_union.append(items_mostrar[indice_sel])
                if key == '\x18' and en_cola_view and items_mostrar: # CTRL+X
                    cola_union.remove(items_mostrar[indice_sel])
                if key == readchar.key.BACKSPACE:
                    filtro = filtro[:-1]; indice_sel = 0
                elif len(key) == 1 and key.isprintable():
                    filtro += key; indice_sel = 0

        nombre_f = Prompt.ask("\nNombre del archivo unido", default="fusion_ninja.pdf")
        self.proceder_a_unir(cola_union, nombre_f)

    def render_ui(self, disp_view, cola_view, seleccionado, filtro, en_cola):
        inst = Table.grid(expand=True)
        inst.add_column(style="bold yellow", width=15)
        inst.add_row(" MODO:", "[bold green]GESTIÓN COLA[/bold green]" if en_cola else "[bold blue]SELECCIÓN[/bold blue]")
        inst.add_row(" TECLAS:", "[TAB] Switch | [ENTER] Añadir | [CTRL+X] Quitar | [CTRL+S] Unir")

        def render_lista(lista, sel, es_activo):
            if not lista: return "[dim]Vacío...[/dim]"
            txt = ""
            for i, nombre in enumerate(lista):
                estilo = "bold black on cyan" if (i == sel and es_activo) else "white"
                txt += f"[{estilo}] {nombre} [/{estilo}]\n"
            return txt

        grid = Table.grid(expand=True, padding=1)
        grid.add_column(ratio=5); grid.add_column(ratio=5)
        grid.add_row(
            Panel(render_lista(disp_view, seleccionado, not en_cola), title="📂 DISPONIBLES", border_style="blue"),
            Panel(render_lista(cola_view, seleccionado, en_cola), title="🛒 COLA", border_style="green")
        )
        
        layout = Table.grid(expand=True)
        layout.add_row(Panel(inst, title="🥷 MANDOS", border_style="bright_magenta"))
        layout.add_row(grid)
        return Panel(layout, title=f" PDF NINJA (Filtro: {filtro}) ")

    def proceder_a_unir(self, lista, nombre_final):
        if not nombre_final.lower().endswith(".pdf"): nombre_final += ".pdf"
        doc_u = fitz.open()
        for n in tqdm(lista, desc="Fusionando"):
            temp = self.abrir_y_limpiar(os.path.join(self.entrada, n))
            with fitz.open(temp) as m: doc_u.insert_pdf(m)
            if temp.endswith(".tmp"): os.remove(temp)
        doc_u.save(os.path.join(self.salida, nombre_final), garbage=4, deflate=True)
        doc_u.close()

    def ejecutar_mision(self, comprimir=False):
        archivos = [f for f in os.listdir(self.entrada) if f.endswith('.pdf')]
        if not archivos:
            console.print("[yellow]⚠️ No hay archivos para procesar.[/yellow]")
            return

        for nombre in tqdm(archivos, desc="Modo Ninja"):
            r_in = os.path.join(self.entrada, nombre)
            r_out = os.path.join(self.salida, nombre)
            password = "" # Empezamos sin contraseña
            
            intentar_de_nuevo = True
            while intentar_de_nuevo:
                try:
                    # INTENTO 1: Abrir con pikepdf (quitando restricciones de dueño)
                    with pikepdf.open(r_in, password=password) as pdf:
                        pdf.save(r_out)
                    
                    # INTENTO 2: Optimizar con fitz (PyMuPDF)
                    doc = fitz.open(r_out)
                    doc.save(r_out, garbage=4 if comprimir else 3, deflate=comprimir, incremental=False)
                    doc.close()
                    
                    console.print(f"[bold green]✅ Procesado:[/bold green] {nombre}")
                    intentar_de_nuevo = False

                except pikepdf.PasswordError:
                    # Si el error es de contraseña, la pedimos al usuario
                    console.print(f"\n[bold red]🔑 El archivo '{nombre}' tiene contraseña de apertura.[/bold red]")
                    password = Prompt.ask(f"Introduce la contraseña para este PDF (o pulsa Enter para saltar)", password=True)
                    
                    if not password: 
                        console.print("[yellow]Saltando archivo...[/yellow]")
                        intentar_de_nuevo = False
                
                except Exception as e:
                    # Otros errores (archivo corrupto, etc.)
                    console.print(f"[bold red]❌ Error inesperado en {nombre}:[/bold red] {e}")
                    intentar_de_nuevo = False

    def dividir_pdf(self):
        archivos = [f for f in os.listdir(self.entrada) if f.endswith('.pdf')]
        if not archivos: return
        archivo_sel = Prompt.ask("Archivo", choices=archivos)
        with fitz.open(os.path.join(self.entrada, archivo_sel)) as doc:
            desde = IntPrompt.ask("Desde página", default=1)
            hasta = IntPrompt.ask("Hasta página", default=doc.page_count)
            nuevo = fitz.open()
            nuevo.insert_pdf(doc, from_page=max(0, desde-1), to_page=min(doc.page_count-1, hasta-1))
            nuevo.save(os.path.join(self.salida, f"split_{archivo_sel}"))
            console.print("[green]División completada.[/green]")

def menu():
    ninja = PDFNinjaMaster()
    while True:
        #os.system('cls' if os.name == 'nt' else 'clear')         
        console.print("\n" + "="*40)
        console.print(Panel.fit(" 🥷  PDF NINJA - MASTER CODE ", style="bold green"))
        console.print("1. Desbloqueo Limpio")
        console.print("2. Desbloqueo + COMPRESIÓN")
        console.print("3. Herramienta: UNIR PDFs")
        console.print("4. Herramienta: DIVIDIR PDF")
        console.print("5. Imágenes a PDF")
        console.print("6. Salir")
        
        op = Prompt.ask("\n[bold yellow]Elige una misión[/bold yellow]", choices=["1", "2", "3", "4", "5", "6"])
        
        if op == "1": 
            ninja.ejecutar_mision()
        elif op == "2": 
            ninja.ejecutar_mision(comprimir=True)
        elif op == "3": 
            ninja.unir_pdfs_interactivo()
        elif op == "4": 
            ninja.dividir_pdf()
        elif op == "5": 
            ninja.imagenes_a_pdf()
        elif op == "6": 
            console.print("[bold red]Saliendo del dojo... 👋[/bold red]")
            break
        
        # Añadimos una pausa para que el usuario pueda leer los resultados
        console.print("\n[dim]Misión finalizada. Presiona ENTER para volver al menú...[/dim]")
        input()

if __name__ == "__main__":
    menu()