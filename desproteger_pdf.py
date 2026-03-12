import os, sys, subprocess, fitz, pikepdf
from tqdm import tqdm
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from rich.prompt import Prompt, IntPrompt

def instalar_dependencias():
    libs = ["pymupdf", "rich", "tqdm", "readchar", "pikepdf"]
    for lib in libs:
        try:
            __import__(lib if lib != "pymupdf" else "fitz")
        except ImportError:
            subprocess.call([sys.executable, "-m", "pip", "install", "-q", lib])

instalar_dependencias()
import readchar
console = Console()

class PDFNinjaMaster:
    def __init__(self):
        self.entrada = "./pdfs_protegidos"
        self.salida = "./pdfs_libres"
        for d in [self.entrada, self.salida]:
            if not os.path.exists(d): os.makedirs(d)

    def unir_pdfs_interactivo(self):
        todos = sorted([f for f in os.listdir(self.entrada) if f.endswith('.pdf')])
        if not todos: return

        cola_union = []
        indice_sel = 0
        filtro = ""
        en_cola_view = False 

        with Live(self.render_ui([], [], 0, "", False), refresh_per_second=15, screen=True) as live:
            while True:
                # 1. ACTUALIZAR LISTAS SEGÚN EL FILTRO
                if en_cola_view:
                    # En la cola, filtramos sobre lo que ya hay
                    items_mostrar = [(i, f) for i, f in enumerate(cola_union) if filtro.lower() in f.lower()]
                else:
                    # En disponibles, filtramos lo que NO está en la cola
                    items_mostrar = [f for f in todos if filtro.lower() in f.lower() and f not in cola_union]
                
                # Ajuste de seguridad del índice
                if not items_mostrar: indice_sel = 0
                elif indice_sel >= len(items_mostrar): indice_sel = len(items_mostrar) - 1

                # Renderizar la interfaz
                live.update(self.render_ui(
                    items_mostrar if not en_cola_view else [f for f in todos if f not in cola_union], 
                    items_mostrar if en_cola_view else [(i, f) for i, f in enumerate(cola_union)], 
                    indice_sel, filtro, en_cola_view
                ))
                
                # 2. CAPTURA DE TECLA (BLOQUEANTE)
                key = readchar.readkey()

                # --- SALIDA INMEDIATA (ESC) ---
                if key in [readchar.key.ESC, '\x1b']:
                    return # Sale de la unión al menú principal sin preguntar

                # --- GUARDAR (CTRL + S) ---
                if key == '\x13': 
                    if cola_union: break
                    continue

                # --- CAMBIO DE PANEL (TAB) ---
                if key == readchar.key.TAB:
                    en_cola_view = not en_cola_view
                    filtro = "" # Limpiamos búsqueda para ver todo el panel nuevo
                    indice_sel = 0
                    continue

                # --- NAVEGACIÓN (FLECHAS) ---
                if key == readchar.key.UP and items_mostrar:
                    indice_sel = (indice_sel - 1) % len(items_mostrar)
                    continue
                if key == readchar.key.DOWN and items_mostrar:
                    indice_sel = (indice_sel + 1) % len(items_mostrar)
                    continue

                # --- ACCIÓN ENTER ---
                if key == readchar.key.ENTER:
                    if not en_cola_view and items_mostrar:
                        cola_union.append(items_mostrar[indice_sel])
                        # No limpiamos filtro para poder añadir archivos similares rápido
                    elif en_cola_view:
                        # Si pulsamos Enter en la cola, volvemos a la selección
                        en_cola_view = False
                        filtro = ""
                        indice_sel = 0
                    continue

                # --- ELIMINAR (Solo si estamos en el panel de la COLA) ---
                if key == '\x18' and en_cola_view: # CTRL + X
                    if items_mostrar:
                        idx_real, _ = items_mostrar[indice_sel]
                        cola_union.pop(idx_real)
                    continue

                # --- BUSCADOR ---
                if key == readchar.key.BACKSPACE:
                    filtro = filtro[:-1]
                elif len(key) == 1 and key.isprintable():
                    filtro += key
                    indice_sel = 0

        # FINALIZACIÓN
        nombre_f = Prompt.ask("\nNombre final de la unión", default="unificado_ninja.pdf")
        if not nombre_f.lower().endswith(".pdf"): nombre_f += ".pdf"
        self.proceder_a_unir(cola_union, nombre_f)

    def render_ui(self, disp_view, cola_view, seleccionado, filtro, en_cola):
        inst = Table.grid(expand=True)
        inst.add_column(style="bold yellow", width=15)
        inst.add_column(style="white")
        
        estado = "[bold green]MODO GESTIÓN COLA[/bold green]" if en_cola else "[bold blue]MODO SELECCIÓN[/bold blue]"
        inst.add_row(" PANEL ACTIVO:", estado)
        inst.add_row(" [TAB]", "Cambiar entre Disponibles y Cola")
        inst.add_row(" [ENTER]", "Añadir (si estás en Izq) / Confirmar y volver (si estás en Der)")
        inst.add_row(" [CTRL+X]", "Eliminar de la cola (Solo en panel derecho)")
        inst.add_row(" [ESC]", "SALIR AL MENÚ")
        inst.add_row(" [CTRL+S]", "GUARDAR Y FINALIZAR")

        def render_lista(lista, sel):
            if not lista: return "[dim]No hay archivos...[/dim]"
            inicio = max(0, sel - 5)
            fin = inicio + 12
            txt = ""
            for i, item in enumerate(lista[inicio:fin]):
                idx_actual = i + inicio
                prefix = "[bold cyan]→ [/bold cyan]" if idx_actual == sel else "  "
                # Manejar si es tupla (cola) o string (disponibles)
                nombre = item[1] if isinstance(item, tuple) else item
                num = f"[dim]{item[0]+1:02d}. [/dim]" if isinstance(item, tuple) else ""
                estilo = "black on white" if idx_actual == sel else "white"
                txt += f"{prefix}[{estilo}]{num}{nombre}[/{estilo}]\n"
            return txt

        grid = Table.grid(expand=True, padding=1)
        grid.add_column(ratio=5); grid.add_column(ratio=5)
        grid.add_row(
            Panel(render_lista(disp_view, seleccionado if not en_cola else -1), 
                  title=f"📂 DISPONIBLES {'(BUSCAR: '+filtro+')' if not en_cola else ''}", border_style="blue" if not en_cola else "dim"),
            Panel(render_lista(cola_view, seleccionado if en_cola else -1), 
                  title=f"🛒 COLA DE UNIÓN {'(BUSCAR: '+filtro+')' if en_cola else ''}", border_style="green" if en_cola else "dim")
        )
        
        layout = Table.grid(expand=True)
        layout.add_row(Panel(inst, title="🥷 MANDOS", border_style="bright_magenta"))
        layout.add_row(grid)
        return Panel(layout, title="[bold magenta] PDF NINJA JOINER [/bold magenta]")

    def proceder_a_unir(self, lista, nombre_final):
        doc_u = fitz.open()
        for n in tqdm(lista, desc="Uniendo"):
            with fitz.open(os.path.join(self.entrada, n)) as m: doc_u.insert_pdf(m)
        doc_u.save(os.path.join(self.salida, nombre_final), garbage=4, deflate=True)
        doc_u.close()
        console.print(f"[bold green]✅ UNIÓN COMPLETADA.[/bold green]\n")

    def ejecutar_mision(self, comprimir=False):
        archivos = [f for f in os.listdir(self.entrada) if f.endswith('.pdf')]
        for nombre in tqdm(archivos, desc="Operación Ninja"):
            r_in, r_out = os.path.join(self.entrada, nombre), os.path.join(self.salida, nombre)
            print("Hola Mundo")
            if os.path.exists(r_out): continue
            try:
                doc = fitz.open(r_in)
                doc.save(r_out, garbage=4 if comprimir else 3, deflate=comprimir)
                doc.close()
            except Exception as e:
                print(f"Fallo: {e}")

    def dividir_pdf(self):
        archivos = [f for f in os.listdir(self.entrada) if f.endswith('.pdf')]
        if not archivos: return
        archivo_sel = Prompt.ask("Archivo a dividir", choices=archivos)
        desde = IntPrompt.ask("Inicio"); hasta = IntPrompt.ask("Fin")
        with fitz.open(os.path.join(self.entrada, archivo_sel)) as doc:
            nuevo = fitz.open(); nuevo.insert_pdf(doc, from_page=desde-1, to_page=hasta-1)
            nuevo.save(os.path.join(self.salida, f"extraido_{archivo_sel}")); nuevo.close()

def menu():
    ninja = PDFNinjaMaster()
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        console.print(Panel.fit(" 🥷  PDF NINJA - EL CÓDIGO MAESTRO ", style="bold green"))
        console.print("1. Desbloqueo Inteligente\n2. Desbloqueo + COMPRESIÓN\n3. Herramienta: UNIR PDFs\n4. Herramienta: DIVIDIR PDF\n5. Salir")
        op = Prompt.ask("\nElige", choices=["1", "2", "3", "4", "5"])
        if op == "1": ninja.ejecutar_mision()
        elif op == "2": ninja.ejecutar_mision(comprimir=True)
        elif op == "3": ninja.unir_pdfs_interactivo()
        elif op == "4": ninja.dividir_pdf()
        elif op == "5": break

if __name__ == "__main__":
    menu()