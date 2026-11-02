"""Programas de ejemplo que se pueden abrir desde el menú Más > Ejemplos."""

EXAMPLES = {
    "Hola mundo (consola)": '''nombre = input("¿Cómo te llamas? ")
print(f"¡Hola, {nombre}! Bienvenido a PyStudio.")
for i in range(1, 6):
    print(i, "x", i, "=", i * i)
''',

    "Calculadora (tkinter)": '''import tkinter as tk

ventana = tk.Tk()
ventana.title("Calculadora")
ventana.configure(bg="#202124")

pantalla = tk.Entry(ventana, font=("Arial", 24), justify="right")
pantalla.pack(fill="x", padx=8, pady=8)


def pulsar(valor):
    if valor == "C":
        pantalla.delete(0, tk.END)
    elif valor == "=":
        try:
            resultado = eval(pantalla.get())
            pantalla.delete(0, tk.END)
            pantalla.insert(0, str(resultado))
        except Exception:
            pantalla.delete(0, tk.END)
            pantalla.insert(0, "Error")
    else:
        pantalla.insert(tk.END, valor)


teclas = ["7", "8", "9", "/",
          "4", "5", "6", "*",
          "1", "2", "3", "-",
          "0", ".", "=", "+",
          "C"]

marco = tk.Frame(ventana, bg="#202124")
marco.pack(fill="both", expand=True, padx=8, pady=8)
for i, t in enumerate(teclas):
    color = "#ff9500" if t in "/*-+=" else "#3c4043"
    b = tk.Button(marco, text=t, font=("Arial", 20), bg=color, fg="white",
                  command=lambda v=t: pulsar(v))
    b.grid(row=i // 4, column=i % 4, sticky="nsew", padx=3, pady=3)
marco.columnconfigure(range(4), weight=1)
marco.rowconfigure(range(5), weight=1)

ventana.mainloop()
''',

    "Contador (tkinter)": '''import tkinter as tk

root = tk.Tk()
root.title("Contador")

cuenta = tk.IntVar(value=0)

tk.Label(root, text="Contador", font=("Arial", 22, "bold")).pack(pady=10)
tk.Label(root, textvariable=cuenta, font=("Arial", 48), fg="#1a73e8").pack(pady=10)

fila = tk.Frame(root)
fila.pack(pady=10)
tk.Button(fila, text="-1", width=6, command=lambda: cuenta.set(cuenta.get() - 1)).pack(side="left", padx=5)
tk.Button(fila, text="Reiniciar", command=lambda: cuenta.set(0)).pack(side="left", padx=5)
tk.Button(fila, text="+1", width=6, command=lambda: cuenta.set(cuenta.get() + 1)).pack(side="left", padx=5)

root.mainloop()
''',

    "Formulario con mensajes (tkinter)": '''import tkinter as tk
from tkinter import messagebox, ttk

root = tk.Tk()
root.title("Registro")

tk.Label(root, text="Nombre:").grid(row=0, column=0, sticky="w", padx=6, pady=6)
nombre = tk.Entry(root)
nombre.grid(row=0, column=1, sticky="ew", padx=6, pady=6)

tk.Label(root, text="Edad:").grid(row=1, column=0, sticky="w", padx=6, pady=6)
edad = tk.Entry(root)
edad.grid(row=1, column=1, sticky="ew", padx=6, pady=6)

tk.Label(root, text="Ciudad:").grid(row=2, column=0, sticky="w", padx=6, pady=6)
ciudad = ttk.Combobox(root, values=["Bogotá", "Medellín", "Cali", "Barranquilla"])
ciudad.grid(row=2, column=1, sticky="ew", padx=6, pady=6)

acepta = tk.BooleanVar()
tk.Checkbutton(root, text="Acepto los términos", variable=acepta).grid(row=3, column=0, columnspan=2, pady=6)


def enviar():
    if not acepta.get():
        messagebox.showwarning("Atención", "Debes aceptar los términos")
        return
    if messagebox.askyesno("Confirmar", f"¿Registrar a {nombre.get()}?"):
        messagebox.showinfo("Listo", f"{nombre.get()} ({edad.get()} años) de {ciudad.get()} registrado.")


tk.Button(root, text="Enviar", bg="#1a73e8", fg="white", command=enviar).grid(row=4, column=0, columnspan=2, pady=10)
root.mainloop()
''',

    "Lista de tareas (tkinter)": '''import tkinter as tk

root = tk.Tk()
root.title("Tareas")

entrada = tk.Entry(root, font=("Arial", 16))
entrada.pack(fill="x", padx=8, pady=8)

lista = tk.Listbox(root, font=("Arial", 16))


def agregar(event=None):
    texto = entrada.get().strip()
    if texto:
        lista.insert(tk.END, texto)
        entrada.delete(0, tk.END)


def borrar():
    for i in reversed(lista.curselection()):
        lista.delete(i)


entrada.bind("<Return>", agregar)
botones = tk.Frame(root)
botones.pack(fill="x", padx=8)
tk.Button(botones, text="Agregar", command=agregar).pack(side="left", expand=True, fill="x")
tk.Button(botones, text="Borrar seleccionada", command=borrar).pack(side="left", expand=True, fill="x")
lista.pack(fill="both", expand=True, padx=8, pady=8)

root.mainloop()
''',

    "Dibujo en Canvas (tkinter)": '''import tkinter as tk
import random

root = tk.Tk()
root.title("Canvas")
canvas = tk.Canvas(root, bg="white")
canvas.pack(fill="both", expand=True)

colores = ["red", "blue", "green", "orange", "purple"]


def dibujar():
    canvas.delete("all")
    for _ in range(25):
        x, y = random.randint(0, 300), random.randint(0, 400)
        r = random.randint(10, 50)
        canvas.create_oval(x - r, y - r, x + r, y + r, fill=random.choice(colores))
    canvas.create_text(150, 30, text="¡Toca el botón!", font=("Arial", 18, "bold"))


tk.Button(root, text="Dibujar de nuevo", command=dibujar).pack(fill="x")
dibujar()
root.mainloop()
''',

    "Reloj con after() (tkinter)": '''import tkinter as tk
import time

root = tk.Tk()
root.title("Reloj")
etiqueta = tk.Label(root, font=("Courier", 40, "bold"), fg="#0f9d58")
etiqueta.pack(expand=True)


def actualizar():
    etiqueta.config(text=time.strftime("%H:%M:%S"))
    root.after(1000, actualizar)


actualizar()
root.mainloop()
''',

    "Adivina el número (consola)": '''import random

secreto = random.randint(1, 100)
intentos = 0
print("Estoy pensando en un número del 1 al 100.")
while True:
    intento = int(input("Tu número: "))
    intentos += 1
    if intento < secreto:
        print("Más alto")
    elif intento > secreto:
        print("Más bajo")
    else:
        print(f"¡Correcto! Lo lograste en {intentos} intentos.")
        break
''',
}
